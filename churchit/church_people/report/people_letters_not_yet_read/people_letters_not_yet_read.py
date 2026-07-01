import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "parent", "fieldtype": "Link", "label": "From", "options": "Person", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": "Date", "width": 100},
		{"fieldname": "share_with_church", "fieldtype": "Check", "label": "Share w/ Church?", "width": 120},
		{"fieldname": "shared_date", "fieldtype": "Date", "label": "Shared Date", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Is Private?", "width": 100},
		{"fieldname": "file", "fieldtype": "Link", "label": "File", "options": "File", "width": 150},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]


def get_data():
	return frappe.db.sql(
		"""
		SELECT
			`tabLetter`.parent,
			`tabLetter`.date,
			`tabLetter`.share_with_church,
			`tabLetter`.shared_date,
			`tabLetter`.is_private,
			`tabLetter`.file,
			`tabLetter`.content
		FROM `tabLetter`
		INNER JOIN `tabPerson` ON `tabPerson`.name = `tabLetter`.parent
		WHERE `tabLetter`.parenttype = 'Person'
			AND `tabLetter`.share_with_church = 1
			AND `tabLetter`.shared_date IS NULL
		ORDER BY `tabLetter`.parent
		""",
		as_dict=True,
	)
