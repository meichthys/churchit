import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "parent", "fieldtype": "Link", "label": "From", "options": "Missionary", "width": 150},
	]
	cols += [
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 100},
		{"fieldname": "share_with_church", "fieldtype": "Check", "label": "Share w/ Church?", "width": 120},
		{"fieldname": "shared_date", "fieldtype": "Date", "label": "Shared Date", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Is Private?", "width": 100},
		{"fieldname": "file", "fieldtype": "Link", "label": "File", "options": "File", "width": 150},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]
	return cols


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(filters, "Missionary", "`tabMissionary`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT
			`tabLetter`.parent,
			`tabLetter`.date,
			`tabLetter`.share_with_church,
			`tabLetter`.shared_date,
			`tabLetter`.is_private,
			`tabLetter`.file,
			`tabLetter`.content
		FROM `tabLetter`
		INNER JOIN `tabMissionary` ON `tabMissionary`.name = `tabLetter`.parent
		WHERE `tabLetter`.parenttype = 'Missionary'
			{church_condition}
		ORDER BY `tabLetter`.parent
		""",
		values,
		as_dict=True,
	)
