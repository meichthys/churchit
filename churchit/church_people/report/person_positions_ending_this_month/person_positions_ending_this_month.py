import frappe
from frappe import _
from frappe.utils import add_days, today

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
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
	"""Terms that end from today to 60 days ahead, or between the From and To dates."""
	filters = filters or {}
	from_date = filters.get("from_date") or today()
	to_date = filters.get("to_date") or add_days(from_date, 60)

	Position = frappe.qb.DocType("Position")
	Person = frappe.qb.DocType("Person")

	query = (
		frappe.qb.from_(Position)
		.join(Person)
		.on(Person.name == Position.parent)
		.select(
			Person.name,
			Person.church,
			Position.position,
			Position.start_date,
			Position.end_date,
			Position.notes,
		)
		.where(
			(Position.parenttype == "Person")
			& Position.end_date.isnotnull()
			& (Position.end_date >= from_date)
			& (Position.end_date <= to_date)
		)
		.orderby(Position.end_date)
		.orderby(Person.name)
	)
	return scoped(query, Person, filters).run(as_dict=True)
