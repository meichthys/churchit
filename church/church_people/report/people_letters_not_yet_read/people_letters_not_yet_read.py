import frappe


def execute(filters=None):
	return get_columns(), get_data()


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
	church_condition = ""
	values = {}

	if "System Manager" not in frappe.get_roles():
		church_condition = """AND `tabPerson`.church IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

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
		INNER JOIN `tabPerson` ON `tabPerson`.name = `tabLetter`.parent
		WHERE `tabLetter`.parenttype = 'Person'
			AND `tabLetter`.share_with_church = 1
			AND `tabLetter`.shared_date IS NULL
			{church_condition}
		ORDER BY `tabLetter`.parent
		""",
		values,
		as_dict=True,
	)
