# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Recurring Functions: a template Function creates its occurrences ahead of time.

A Function with Automatically Recreate is a template. Once a day, each template gets every
occurrence its rule gives from the day after its latest occurrence (or today, if later) up to
its horizon and Repeat Until, so the calendar shows them weeks ahead. An occurrence copies the
template through `apply_template`, and the template's Requested and Approved Room Bookings
come along, moved to the new date. A deleted occurrence deletes its room bookings and adds its
date to the template's Skip Dates (`Function.on_trash`), so it is not made again.
"""

from datetime import date, datetime, time, timedelta

import frappe
from dateutil.rrule import DAILY, FR, MO, MONTHLY, SA, SU, TH, TU, WE, WEEKLY, YEARLY, rrule
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, format_datetime, get_datetime, getdate

from churchit.church_ministries.doctype.function.function import apply_template

FREQUENCIES = {"Daily": DAILY, "Weekly": WEEKLY, "Monthly": MONTHLY, "Yearly": YEARLY}
WEEKDAYS = {
	"Monday": MO,
	"Tuesday": TU,
	"Wednesday": WE,
	"Thursday": TH,
	"Friday": FR,
	"Saturday": SA,
	"Sunday": SU,
}
WEEKS_OF_MONTH = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Last": -1}


def create_scheduled_functions() -> None:
	"""Daily job: create each template's missing occurrences."""
	today = getdate()
	# church-scope: scheduled daily job, site-wide by design; each copy takes its template's church
	for name in frappe.get_all("Function", filters={"auto_repeat": 1}, pluck="name"):
		frappe.db.savepoint("recurrence")
		try:
			create_missing_occurrences(frappe.get_doc("Function", name), today)
		except Exception:
			frappe.db.rollback(save_point="recurrence")
			frappe.log_error(
				title=f"Auto-create next Function failed for {name}",
				reference_doctype="Function",
				reference_name=name,
			)


def create_missing_occurrences(template: Document, today: date) -> None:
	"""Create *template*'s occurrences after its latest one, up to its horizon and Repeat Until."""
	# church-scope: the occurrences of one template, which all take the template's church
	latest = frappe.get_all(
		"Function",
		filters={"source_template": template.name},
		order_by="start_date desc",
		limit=1,
		pluck="start_date",
	)
	start = max(getdate(add_days(latest[0] if latest else template.start_date, 1)), today)
	end = today + timedelta(weeks=cint(template.repeat_horizon_weeks))
	if template.repeat_until:
		end = min(end, getdate(template.repeat_until))

	for start_date in get_occurrence_dates(template, start, end):
		create_occurrence(template, start_date)


def get_occurrence_dates(template, start: date, end: date) -> list[date]:
	"""The dates *template*'s rule gives from *start* to *end*, both included, less its skip dates."""
	first = getdate(template.start_date)
	parts = {}
	if template.repeat_frequency == "Monthly" and template.repeat_monthly_by == "Weekday":
		week = WEEKS_OF_MONTH[template.repeat_week_of_month]
		parts["byweekday"] = WEEKDAYS[template.repeat_day_of_week](week)
	elif template.repeat_frequency == "Monthly":
		day = cint(template.repeat_month_day) or first.day
		# The day itself, or the month's last day when the month is shorter.
		parts.update(bymonthday=tuple(range(min(day, 28), day + 1)), bysetpos=-1)
	elif template.repeat_frequency == "Weekly" and template.repeat_day_of_week:
		parts["byweekday"] = WEEKDAYS[template.repeat_day_of_week]

	rule = rrule(
		FREQUENCIES[template.repeat_frequency],
		dtstart=datetime.combine(first, time.min),
		interval=cint(template.repeat_interval) or 1,
		**parts,
	)
	skipped = {getdate(row.date) for row in template.skip_dates}
	dates = rule.between(datetime.combine(start, time.min), datetime.combine(end, time.min), inc=True)
	return [day.date() for day in dates if day.date() not in skipped]


def create_occurrence(template: Document, start_date: date) -> Document:
	"""A new Function from *template* on *start_date*, with the template's room bookings."""
	values = apply_template(template.name, str(start_date))
	values.update(
		doctype="Function",
		function_name=template.function_name,
		type=template.type,
		start_date=start_date,
		# A multi-day function, such as a weekend retreat, keeps its length.
		end_date=add_days(start_date, date_diff(template.end_date, template.start_date))
		if template.end_date
		else None,
		source_template=template.name,
		auto_repeat=0,
		publish=template.publish,
		is_link_only=template.is_link_only,
		church=template.church,
	)
	if not template.all_day:
		values.update(start_time=template.start_time, end_time=template.end_time)

	function = frappe.get_doc(values).insert(ignore_permissions=True)
	copy_room_bookings(template, function, date_diff(start_date, template.start_date))
	return function


def copy_room_bookings(template: Document, function: Document, days: int) -> None:
	"""Book *function* the rooms *template* has, *days* later. A clash leaves a Comment instead."""
	# church-scope: a template's bookings follow it, whichever church owns the room
	for name in frappe.get_all(
		"Room Booking",
		filters={"function": template.name, "status": ("in", ("Requested", "Approved"))},
		pluck="name",
	):
		booking = frappe.copy_doc(frappe.get_doc("Room Booking", name))
		booking.start_datetime = add_days(get_datetime(booking.start_datetime), days)
		booking.end_datetime = add_days(get_datetime(booking.end_datetime), days)
		booking.function = function.name
		booking.status = "Requested"
		booking.request_anyway = 1
		try:
			booking.insert(ignore_permissions=True)
		except (frappe.ValidationError, frappe.PermissionError):
			function.add_comment(
				"Comment",
				_("{0} was not booked from {1} to {2}: the room is taken or cannot be booked.").format(
					frappe.db.get_value("Room", booking.room, "room_name")
					if booking.room
					else _("Equipment"),
					format_datetime(booking.start_datetime),
					format_datetime(booking.end_datetime),
				),
			)
