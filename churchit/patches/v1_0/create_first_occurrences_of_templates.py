# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each recurring template from today on its first occurrence, and set every template's total to 0.

A template is now a rule, not an event: its first date is a real occurrence, which check-in, reports and
calendars read, and its people are a roster. Before, the occurrences began the day after the template, so
the template alone held its first date. Safe to run twice: a date that has an occurrence gets no second.
"""

import frappe
from frappe.utils import getdate

from churchit.church_ministries.recurrence import (
	create_missing_occurrences,
	create_occurrence,
	get_occurrence_dates,
)


def execute():
	Function = frappe.qb.DocType("Function")
	(
		frappe.qb.update(Function)
		.set(Function.attendance_total, 0)
		.where((Function.auto_repeat == 1) & (Function.attendance_total != 0))
		.run()
	)

	today = getdate()
	# church-scope: a patch over every church; each occurrence takes its template's church
	for name in frappe.get_all(
		"Function", filters={"auto_repeat": 1, "start_date": (">=", today)}, pluck="name"
	):
		frappe.db.savepoint("first_occurrence")
		try:
			create_first_occurrence(frappe.get_doc("Function", name), today)
		except Exception:
			frappe.db.rollback(save_point="first_occurrence")
			frappe.log_error(
				title=f"First occurrence not created for {name}",
				reference_doctype="Function",
				reference_name=name,
			)


def create_first_occurrence(template, today) -> None:
	"""Create *template*'s occurrence on its Start Date when its rule gives that date and none is there."""
	if not frappe.db.exists("Function", {"source_template": template.name}):
		create_missing_occurrences(template, today)
		return

	start = getdate(template.start_date)
	if get_occurrence_dates(template, start, start) and not frappe.db.exists(
		"Function", {"source_template": template.name, "start_date": start}
	):
		create_occurrence(template, start)
