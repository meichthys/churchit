import frappe
from frappe.utils import today

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 180},
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 180},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": "Notes", "width": 300},
	]


def get_data(filters=None):
	as_of = today()

	Position = frappe.qb.DocType("Position")
	Person = frappe.qb.DocType("Person")

	return (
		frappe.qb.from_(Position)
		.join(Person)
		.on(Person.name == Position.parent)
		.select(
			Person.name,
			Position.position,
			Position.start_date,
			Position.end_date,
			Position.notes,
		)
		.where(
			(Position.parenttype == "Person")
			& Position.position.isnotnull()
			& (Position.start_date <= as_of)
			& (Position.end_date.isnull() | (Position.end_date >= as_of))
		)
		.orderby(Person.name)
		.orderby(Position.start_date)
		.run(as_dict=True)
	)
