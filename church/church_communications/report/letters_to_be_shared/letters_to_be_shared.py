import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "parenttype", "fieldtype": "Data", "label": "Type", "width": 120},
		{"fieldname": "parent", "fieldtype": "Dynamic Link", "label": "From", "options": "parenttype", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": "Received", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Private?", "width": 80},
		{"fieldname": "file", "fieldtype": "Data", "label": "File", "width": 200},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT
			`tabLetter`.parenttype,
			`tabLetter`.parent,
			`tabLetter`.date,
			`tabLetter`.is_private,
			COALESCE(`tabLetter`.file, ''),
			`tabLetter`.content,
			`tabLetter`.name
		FROM `tabLetter`
		WHERE `tabLetter`.share_with_church = 1
			AND `tabLetter`.shared_date IS NULL
		""",
		as_dict=True,
	)
