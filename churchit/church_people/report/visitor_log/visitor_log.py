import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.utils import add_days, cint, getdate
from pypika import Order

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_people.membership import VISITOR
from churchit.church_scope import get_church_columns, scoped
from churchit.contacts import primary_email_query, primary_phone_query
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "creation", "fieldtype": "Date", "label": _("First Seen"), "width": 120},
		{
			"fieldname": "first_visit",
			"fieldtype": "Link",
			"label": _("First Function"),
			"options": "Function",
			"width": 200,
		},
		{"fieldname": "first_visit_date", "fieldtype": "Date", "label": _("First Visit"), "width": 110},
		{"fieldname": "visit_count", "fieldtype": "Int", "label": _("Visits"), "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": _("Phone"), "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Email"), "width": 200},
	]


def get_data(filters=None):
	days = cint((filters or {}).get("days", 60)) or 60

	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(
			Person.name,
			Person.creation,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			Person.church,
		)
		.where(Coalesce(Person.membership, "").isin(["", VISITOR]))
		.where(Person.creation >= add_days(getdate(), -days))
		.orderby(Person.creation, order=Order.desc)
	)
	rows = scoped(query, Person, filters).run(as_dict=True)

	visits = get_visits([row.name for row in rows])
	for row in rows:
		row.update(visits.get(row.name, {"first_visit": None, "first_visit_date": None, "visit_count": 0}))
	return rows


def get_visits(people: list[str]) -> dict:
	"""Each of *people*'s first counted visit (Function and date) and number of counted visits.

	One query over the attendance rows of these people, not a subquery for each person.
	"""
	if not people:
		return {}

	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")
	attended = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Function.name == Attendance.parent)
		.select(Attendance.person, Attendance.parent, Function.start_date)
		.where(Attendance.person.isin(people))
		.where(Attendance.attendance_type.isin(COUNTED_TYPES) & (Function.start_date <= getdate()))
		.where(Function.auto_repeat == 0)
		.orderby(Function.start_date)
	)

	visits = {}
	for person, function, start_date in attended.run():
		visit = visits.setdefault(
			person, {"first_visit": function, "first_visit_date": start_date, "visit_count": 0}
		)
		visit["visit_count"] += 1
	return visits
