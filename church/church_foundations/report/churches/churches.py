import frappe


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 250},
		{"fieldname": "people", "fieldtype": "Int", "label": "People", "width": 100},
		{"fieldname": "families", "fieldtype": "Int", "label": "Families", "width": 100},
	]


def get_data():
	conditions = ""
	values = {}

	if "System Manager" not in frappe.get_roles():
		conditions += """ AND `tabChurch`.name IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		SELECT
			`tabChurch`.name,
			COUNT(DISTINCT `tabPerson`.name) as people,
			COUNT(DISTINCT `tabFamily`.name) as families
		FROM `tabChurch`
		LEFT JOIN `tabPerson` ON `tabPerson`.church = `tabChurch`.name
		LEFT JOIN `tabFamily` ON `tabFamily`.church = `tabChurch`.name
		WHERE 1=1
			{conditions}
		GROUP BY `tabChurch`.name
		ORDER BY `tabChurch`.name
		""",
		values,
		as_dict=True,
	)
