import frappe

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
		{"fieldname": "position", "fieldtype": "Link", "label": "Position", "options": "Position Type", "width": 160},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Term Start", "width": 110},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "Term End", "width": 110},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	only_active = (filters or {}).get("only_active", 1)

	Position = frappe.qb.DocType("Position")
	Person = frappe.qb.DocType("Person")

	query = (
		frappe.qb.from_(Position)
		.left_join(Person)
		.on(Person.name == Position.parent)
		.select(
			Position.position,
			Position.parent.as_("person"),
			Position.start_date,
			Position.end_date,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
		)
		.where(Position.parenttype == "Person")
		.orderby(Position.position)
		.orderby(Person.full_name)
	)

	if only_active:
		query = query.where(Position.end_date.isnull() | (Position.end_date >= CurDate()))

	return query.run(as_dict=True)
