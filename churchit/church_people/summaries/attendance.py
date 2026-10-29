# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Attendance: when a person first and last attended a function, and how often in the last 90 days."""

import frappe
from frappe.query_builder.functions import Count, Max, Min
from frappe.utils import add_days, getdate, nowdate
from pypika import Case

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_people.summaries import same_church

FIELDS = ("first_attended_on", "last_attended_on", "times_attended_90d")
WINDOW_DAYS = 90


def function_attendees(doc) -> set[str]:
	before = doc.get_doc_before_save()
	rows = [*(doc.get("attendance") or []), *(before.get("attendance") or [] if before else [])]
	return {row.person for row in rows}


SOURCES = {"Function": function_attendees}


def compute(people: list[str]) -> dict[str, dict]:
	"""Each person's first and last attended function up to today, and the functions attended in the window."""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared functions
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	Person = frappe.qb.DocType("Person")
	today = getdate(nowdate())
	since = add_days(today, -WINDOW_DAYS)
	rows = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on((Function.name == Attendance.parent) & (Attendance.parenttype == "Function"))
		.join(Person)
		.on(Person.name == Attendance.person)
		.select(
			Attendance.person,
			Min(Function.start_date).as_("first"),
			Max(Function.start_date).as_("last"),
			Count(Case().when(Function.start_date >= since, Function.name)).distinct().as_("recent"),
		)
		.where(Attendance.person.isin(people) & Attendance.attendance_type.isin(COUNTED_TYPES))
		.where(Function.start_date <= today)
		.where(same_church(Function, Person))
		.groupby(Attendance.person)
		.run(as_dict=True)
	)
	return {
		row.person: {
			"first_attended_on": row.first,
			"last_attended_on": row.last,
			"times_attended_90d": row.recent,
		}
		for row in rows
	}
