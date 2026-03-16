import frappe


def execute(filters=None):
	return get_columns(), get_data()


def get_columns():
	return [
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 200},
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 200},
		{"fieldname": "balance", "fieldtype": "Currency", "label": "Balance", "width": 150},
	]


def get_data():
	church_condition = ""
	values = {}

	if "System Manager" not in frappe.get_roles():
		church_condition = """AND church IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		SELECT church, fund, balance
		FROM `tabFund`
		WHERE 1=1
			{church_condition}
		""",
		values,
		as_dict=True,
	)
