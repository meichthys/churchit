import frappe

from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import CurDate, DayOfMonth, Month, Year
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
		{"fieldname": "age", "fieldtype": "Int", "label": "Turning", "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data():
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	return (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on(
			(LifeEvent.parent == Person.name)
			& (LifeEvent.parenttype == "Person")
			& (LifeEvent.event_type == "Birth")
		)
		.select(
			Person.name,
			LifeEvent.date.as_("birthday"),
			(Year(CurDate()) - Year(LifeEvent.date)).as_("age"),
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
		)
		.where(LifeEvent.date.isnotnull() & (Month(LifeEvent.date) == Month(CurDate())))
		.orderby(DayOfMonth(LifeEvent.date))
		.orderby(Person.full_name)
		.run(as_dict=True)
	)
