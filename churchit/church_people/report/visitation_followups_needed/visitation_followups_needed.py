import frappe
from frappe import _

from churchit.church_scope import church_query_filters
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "visit_date", "fieldtype": "Date", "label": _("Visit Date"), "width": 100},
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
	return frappe.get_all(
		"Visitation Log",
		filters={"follow_up_needed": 1, **church_query_filters(filters)},
		fields=["person", "visit_date", "visit_type", "visited_by", "status", "notes"],
		order_by="visit_date desc",
	)
