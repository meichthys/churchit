# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

from calendar import monthrange
from datetime import date, datetime, timedelta

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, add_months, add_years, getdate, now_datetime


WEEKDAY_INDEX = {
	"Monday": 0,
	"Tuesday": 1,
	"Wednesday": 2,
	"Thursday": 3,
	"Friday": 4,
	"Saturday": 5,
	"Sunday": 6,
}


class Function(Document):
	def before_save(self):
		name = self.function_name or ""
		if self.start_date:
			self.title = f"{name}: {self.start_date}"
		else:
			self.title = name

		counted_types = frappe.get_all(
			"Function Attendance Type",
			filters={"type": ["in", ["Confirmed", "Assumed", "Checked-In"]]},
			pluck="name",
		)
		self.attendance_total = sum(
			1 for row in (self.attendance or []) if row.attendance_type in counted_types
		)


@frappe.whitelist()
def apply_template(source_name):
	# Get template document
	template = frappe.get_doc("Function", source_name)
	template.check_permission("read")
	template_dict = template.as_dict()

	copied_doc = {}

	# Specify which fields to include (whitelist approach)
	include_fields = ["address", "all_day", "description", "associated_ministry"]

	# Copy normal fields
	for field in include_fields:
		if field in template_dict:
			copied_doc[field] = template_dict[field]

	# Copy child tables
	include_child_tables = ["associations", "attendance", "schedule"]
	for child_table in include_child_tables:
		if template_dict.get(child_table):
			copied_doc[child_table] = []
			for child_row in template_dict[child_table]:
				new_row = {}
				for child_field in child_row:
					new_row[child_field] = child_row[child_field]
				copied_doc[child_table].append(new_row)
	return copied_doc


def create_scheduled_functions():
	"""Daily scheduler: for every Function template with auto_repeat=1, create the
	next occurrence once the most recent occurrence has ended."""
	today = getdate()
	templates = frappe.get_all(
		"Function",
		filters={"auto_repeat": 1},
		fields=["name", "repeat_until"],
	)
	for template in templates:
		if template.repeat_until and getdate(template.repeat_until) < today:
			continue
		try:
			_create_next_occurrence(template.name, today)
		except Exception:
			frappe.log_error(
				title=f"Auto-create next Function failed for {template.name}",
				message=frappe.get_traceback(),
			)


def _create_next_occurrence(template_name, today):
	# Find the most recent occurrence already created from this template
	latest = frappe.get_all(
		"Function",
		filters={"source_template": template_name},
		fields=["name", "start_date", "end_date", "end_time", "start_time"],
		order_by="start_date desc, start_time desc",
		limit=1,
	)
	last = latest[0] if latest else None

	# If there is already a future occurrence queued, nothing to do
	if last and getdate(last.start_date) >= today:
		return

	# If the most recent occurrence hasn't ended yet, wait
	if last and not _has_ended(last, today):
		return

	template = frappe.get_doc("Function", template_name)
	reference_date = getdate(last.start_date) if last else getdate(template.start_date or today)
	next_date = _compute_next_date(template, reference_date, today)
	if not next_date:
		return
	if template.repeat_until and next_date > getdate(template.repeat_until):
		return

	new_doc_data = apply_template(template_name)
	new_doc_data["doctype"] = "Function"
	new_doc_data["function_name"] = template.function_name
	new_doc_data["type"] = template.type
	new_doc_data["start_date"] = next_date
	new_doc_data["end_date"] = next_date if template.end_date else None
	if not template.all_day:
		new_doc_data["start_time"] = template.start_time
		new_doc_data["end_time"] = template.end_time
	new_doc_data["source_template"] = template_name
	new_doc_data["auto_repeat"] = 0

	new_function = frappe.get_doc(new_doc_data)
	new_function.insert(ignore_permissions=True)


def _has_ended(occurrence, today):
	end_date = getdate(occurrence.end_date or occurrence.start_date)
	if end_date < today:
		return True
	if end_date > today:
		return False
	# end_date == today: only "ended" if end_time has passed
	if not occurrence.end_time:
		return False
	end_dt = datetime.combine(end_date, _as_time(occurrence.end_time))
	return now_datetime() >= end_dt


def _as_time(value):
	if hasattr(value, "hour"):
		return value
	# timedelta from DB
	if isinstance(value, timedelta):
		total = int(value.total_seconds())
		return (datetime.min + timedelta(seconds=total)).time()
	# string fallback
	return datetime.strptime(str(value), "%H:%M:%S").time()


def _compute_next_date(template, reference_date, today):
	freq = template.repeat_frequency
	# Always advance past today so we never schedule in the past
	candidate = reference_date
	if freq == "Daily":
		candidate = add_days(reference_date, 1)
		while getdate(candidate) < today:
			candidate = add_days(candidate, 1)
		return getdate(candidate)

	if freq == "Weekly":
		target_idx = WEEKDAY_INDEX.get(template.repeat_day_of_week)
		if target_idx is None:
			return None
		candidate = add_days(reference_date, 1)
		# Walk forward to the next matching weekday, at least one day past reference
		while getdate(candidate).weekday() != target_idx or getdate(candidate) < today:
			candidate = add_days(candidate, 1)
		return getdate(candidate)

	if freq == "Monthly":
		day = template.repeat_month_day or getdate(reference_date).day
		candidate = _month_day(add_months(reference_date, 1), day)
		while getdate(candidate) < today:
			candidate = _month_day(add_months(candidate, 1), day)
		return getdate(candidate)

	if freq == "Yearly":
		candidate = add_years(reference_date, 1)
		while getdate(candidate) < today:
			candidate = add_years(candidate, 1)
		return getdate(candidate)

	return None


def _month_day(any_date_in_month, desired_day):
	d = getdate(any_date_in_month)
	last_day = monthrange(d.year, d.month)[1]
	return date(d.year, d.month, min(desired_day, last_day))
