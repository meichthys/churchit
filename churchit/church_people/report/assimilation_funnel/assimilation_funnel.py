# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The people whose first visit falls in a date range, and how far each has come since.

A step is counted for each of them on its own: Came Back (attended again within the weeks the filter gives),
Connected (in a group, or has served) and Member (became a Member from the start of the range until today).
"""

import frappe
from frappe import _
from frappe.utils import add_months, cint, today

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_people.membership import MEMBER, changed_between, living_people_filter
from churchit.church_people.summaries import same_church
from churchit.church_scope import scoped
from churchit.query import DateDiff
from churchit.utils import set_report_link_titles

DEFAULT_WEEKS = 8
STEPS = (
	("first_visit", "First Visit"),
	("came_back", "Came Back"),
	("connected", "Connected"),
	("became_member", "Member"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	counts = [sum(1 for row in data if row[step]) for step, _label in STEPS]
	return columns, data, None, get_chart(counts), get_summary(counts)


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "first_attended_on", "fieldtype": "Date", "label": _("First Visit"), "width": 110},
		{"fieldname": "came_back", "fieldtype": "Check", "label": _("Came Back"), "width": 100},
		{"fieldname": "connected", "fieldtype": "Check", "label": _("Connected"), "width": 100},
		{"fieldname": "became_member", "fieldtype": "Check", "label": _("Member"), "width": 90},
		{
			"fieldname": "membership",
			"fieldtype": "Link",
			"label": _("Membership"),
			"options": "Membership Type",
			"width": 140,
		},
		{"fieldname": "last_attended_on", "fieldtype": "Date", "label": _("Last Attended"), "width": 110},
	]


def get_data(filters) -> list[dict]:
	"""One row per living person whose first visit is in the range, first visit first, with the steps reached."""
	from_date = filters.from_date or add_months(today(), -3)
	rows = get_first_visitors(from_date, filters.to_date or today(), filters)
	people = [row.person for row in rows]
	came_back = get_people_who_came_back(people, cint(filters.weeks) or DEFAULT_WEEKS)
	members = changed_between("membership", MEMBER, from_date, today())
	for row in rows:
		row.first_visit = 1
		row.came_back = int(row.person in came_back)
		row.connected = int(bool(row.group_count or row.last_served_on))
		row.became_member = int(row.person in members)
	return rows


def get_first_visitors(from_date, to_date, filters) -> list[dict]:
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(
			Person.name.as_("person"),
			Person.first_attended_on,
			Person.last_attended_on,
			Person.membership,
			Person.group_count,
			Person.last_served_on,
		)
		.where(Person.first_attended_on[from_date:to_date] & living_people_filter(Person))
		.orderby(Person.first_attended_on)
		.orderby(Person.name)
	)
	return scoped(query, Person, filters).run(as_dict=True)


def get_people_who_came_back(people: list[str], weeks: int) -> set[str]:
	"""Those of *people* who attended a function of their church after their first visit, within *weeks* of it."""
	if not people:
		return set()
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	Person = frappe.qb.DocType("Person")
	days_after = DateDiff(Function.start_date, Person.first_attended_on)
	return set(
		frappe.qb.from_(Attendance)
		.join(Function)
		.on((Function.name == Attendance.parent) & (Attendance.parenttype == "Function"))
		.join(Person)
		.on(Person.name == Attendance.person)
		.select(Attendance.person)
		.distinct()
		.where(Attendance.person.isin(people) & Attendance.attendance_type.isin(COUNTED_TYPES))
		.where((days_after > 0) & (days_after <= weeks * 7) & (Function.start_date <= today()))
		.where(same_church(Function, Person))
		.run(pluck=True)
	)


def get_chart(counts: list[int]) -> dict:
	return {
		"data": {
			"labels": [_(label) for _step, label in STEPS],
			"datasets": [{"name": _("People"), "values": counts}],
		},
		"type": "bar",
		"colors": ["blue"],
	}


def get_summary(counts: list[int]) -> list[dict]:
	return [
		{"value": count, "label": _(label), "datatype": "Int", "indicator": "Blue"}
		for count, (_step, label) in zip(counts, STEPS, strict=True)
	]
