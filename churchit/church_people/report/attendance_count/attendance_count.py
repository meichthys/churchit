# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The living people who attended at least *min_times* functions in a date range.

Saved as a Custom Report, it is a smart list (`smart_lists.REPORT_LISTS`).
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Max
from frappe.utils import cint, getdate, today
from pypika import Order

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_people.membership import living_people_filter
from churchit.church_people.summaries import same_church
from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	if not filters.from_date:
		return columns, []
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "times_attended", "fieldtype": "Int", "label": _("Times Attended"), "width": 130},
		{"fieldname": "last_attended", "fieldtype": "Date", "label": _("Last Attended"), "width": 130},
	]


def get_data(filters: frappe._dict) -> list[dict]:
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	Person = frappe.qb.DocType("Person")
	to_date = min(getdate(filters.to_date or today()), getdate(today()))
	times_attended = Count(Function.name).distinct()

	query = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on((Function.name == Attendance.parent) & (Attendance.parenttype == "Function"))
		.join(Person)
		.on(Person.name == Attendance.person)
		.select(
			Person.name.as_("person"),
			times_attended.as_("times_attended"),
			Max(Function.start_date).as_("last_attended"),
		)
		.where(Attendance.attendance_type.isin(COUNTED_TYPES))
		.where(Function.start_date.between(getdate(filters.from_date), to_date))
		.where(same_church(Function, Person) & living_people_filter(Person))
		.groupby(Person.name)
		.having(times_attended >= max(cint(filters.min_times), 1))
		.orderby(times_attended, order=Order.desc)
		.orderby(Person.name)
	)
	if filters.function_type:
		query = query.where(Function.type == filters.function_type)
	return scoped(query, Person, filters).run(as_dict=True)
