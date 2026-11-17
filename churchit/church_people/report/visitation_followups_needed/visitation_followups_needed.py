import frappe
from frappe import _
from pypika import Order

from churchit.church_people.doctype.visitation_log.visitation_log import has_no_later_visit
from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "visit_date", "fieldtype": "Date", "label": _("Visit Date"), "width": 110},
		{
			"fieldname": "visit_type",
			"fieldtype": "Link",
			"label": _("Visit Type"),
			"options": "Visit Type",
			"width": 130,
		},
		{
			"fieldname": "visited_by",
			"fieldtype": "Link",
			"label": _("Visited By"),
			"options": "Person",
			"width": 160,
		},
		{"fieldname": "status", "fieldtype": "Data", "label": _("Status"), "width": 100},
		{"fieldname": "notes", "fieldtype": "Data", "label": _("Notes"), "width": 320},
	]


def get_data(filters=None):
	Visit = frappe.qb.DocType("Visitation Log")
	query = (
		frappe.qb.from_(Visit)
		.select(
			Visit.person,
			Visit.church,
			Visit.visit_date,
			Visit.visit_type,
			Visit.visited_by,
			Visit.status,
			Visit.notes,
		)
		.where((Visit.follow_up_needed == 1) & has_no_later_visit(Visit))
		.orderby(Visit.visit_date, order=Order.desc)
	)
	return scoped(query, Visit, filters).run(as_dict=True)
