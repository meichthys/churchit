import frappe
from frappe.query_builder.functions import Count, Min
from frappe.utils import cint
from pypika import Interval, Order

from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import CurDate
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "creation", "fieldtype": "Date", "label": "First Seen", "width": 120},
		{"fieldname": "first_visit", "fieldtype": "Link", "label": "First Function", "options": "Function", "width": 200},
		{"fieldname": "first_visit_date", "fieldtype": "Date", "label": "First Visit", "width": 110},
		{"fieldname": "visit_count", "fieldtype": "Int", "label": "Visits", "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	days = cint((filters or {}).get("days", 60)) or 60

	Person = frappe.qb.DocType("Person")
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	def attended():
		return (
			frappe.qb.from_(Attendance)
			.join(Function)
			.on(Function.name == Attendance.parent)
			.where(Attendance.person == Person.name)
		)

	first_visit = attended().select(Attendance.parent).orderby(Function.start_date).limit(1)
	first_visit_date = attended().select(Min(Function.start_date))
	visit_count = (
		frappe.qb.from_(Attendance).select(Count("*")).where(Attendance.person == Person.name)
	)

	return (
		frappe.qb.from_(Person)
		.select(
			Person.name,
			Person.creation,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			first_visit.as_("first_visit"),
			first_visit_date.as_("first_visit_date"),
			visit_count.as_("visit_count"),
		)
		.where(Person.membership_status.isnull() & (Person.creation >= CurDate() - Interval(days=days)))
		.orderby(Person.creation, order=Order.desc)
		.run(as_dict=True)
	)
