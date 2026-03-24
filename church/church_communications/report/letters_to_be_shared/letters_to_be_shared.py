import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "parenttype", "fieldtype": "Data", "label": "Type", "width": 120},
		{"fieldname": "parent", "fieldtype": "Dynamic Link", "label": "From", "options": "parenttype", "width": 150},
		{"fieldname": "date", "fieldtype": "Date", "label": "Received", "width": 100},
		{"fieldname": "is_private", "fieldtype": "Check", "label": "Private?", "width": 80},
		{"fieldname": "file", "fieldtype": "Data", "label": "File", "width": 200},
		{"fieldname": "content", "fieldtype": "Data", "label": "Content", "width": 300},
	]


def get_data(filters=None):
	values = {}
	church_condition = get_church_condition(
		filters, "COALESCE(`tabPerson`.church, `tabMissionary`.church)", values
	)

	return frappe.db.sql(
		f"""
		SELECT
			`tabLetter`.parenttype,
			`tabLetter`.parent,
			`tabLetter`.date,
			`tabLetter`.is_private,
			COALESCE(`tabLetter`.file, ''),
			`tabLetter`.content,
			`tabLetter`.name
		FROM `tabLetter`
		LEFT JOIN `tabPerson` ON `tabLetter`.parenttype = 'Person' AND `tabPerson`.name = `tabLetter`.parent
		LEFT JOIN `tabMissionary` ON `tabLetter`.parenttype = 'Missionary' AND `tabMissionary`.name = `tabLetter`.parent
		WHERE `tabLetter`.share_with_church = 1
			AND `tabLetter`.shared_date IS NULL
			{church_condition}
		""",
		values,
		as_dict=True,
	)
