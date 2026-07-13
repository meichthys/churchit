import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "visit_date", "fieldtype": "Date", "label": "Visit Date", "width": 100},
		{"fieldname": "visit_type", "fieldtype": "Link", "label": "Visit Type", "options": "Visit Type", "width": 130},
		{"fieldname": "visited_by", "fieldtype": "Link", "label": "Visited By", "options": "Person", "width": 160},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 320},
	]


def get_data(filters=None):
	return frappe.get_all(
		"Visitation Log",
		filters={"follow_up_needed": 1},
		fields=["person", "visit_date", "visit_type", "visited_by", "status", "notes"],
		order_by="visit_date desc",
	)
