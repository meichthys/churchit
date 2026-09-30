import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.query import CurDate, Month, Year
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{
			"fieldname": "position",
			"fieldtype": "Link",
			"label": _("Position"),
			"options": "Position Type",
			"width": 180,
		},
		{"fieldname": "start_date", "fieldtype": "Date", "label": _("Start Date"), "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": _("End Date"), "width": 120},
		{"fieldname": "notes", "fieldtype": "Small Text", "label": _("Notes"), "width": 300},
	]


def get_data(filters=None):
	Position = frappe.qb.DocType("Position")
	Person = frappe.qb.DocType("Person")

	query = (
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
			& Position.end_date.isnotnull()
			& (Month(Position.end_date) == Month(CurDate()))
			& (Year(Position.end_date) == Year(CurDate()))
		)
		.orderby(Position.end_date)
		.orderby(Person.name)
	)
	return scoped(query, Person, filters).run(as_dict=True)
