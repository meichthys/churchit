import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 250},
		{"fieldname": "people", "fieldtype": "Int", "label": "People", "width": 100},
		{"fieldname": "families", "fieldtype": "Int", "label": "Families", "width": 100},
	]


def get_data():
	churches = frappe.db.sql(
		"SELECT name FROM `tabChurch` ORDER BY name",
		as_dict=True,
	)
	people_count = frappe.db.count("Person")
	families_count = frappe.db.count("Family")
	for church in churches:
		church["people"] = people_count
		church["families"] = families_count
	return churches
