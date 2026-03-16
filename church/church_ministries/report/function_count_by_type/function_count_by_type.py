import frappe


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "type", "fieldtype": "Data", "label": "Type", "width": 200},
		{"fieldname": "counts", "fieldtype": "Int", "label": "Count", "width": 100},
	]


def get_data(filters):
	filters = filters or {}
	church_condition = ""
	values = {
		"start": filters.get("start"),
		"end": filters.get("end"),
	}

	if "System Manager" not in frappe.get_roles():
		church_condition = """AND church IN (
			SELECT for_value FROM `tabUser Permission`
			WHERE user = %(user)s AND allow = 'Church'
		)"""
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		SELECT type as type, count(name) as counts
		FROM `tabFunction`
		WHERE (start_date IS NULL OR end_date IS NULL OR date(start_date) BETWEEN %(start)s AND %(end)s)
			{church_condition}
		GROUP BY type
		""",
		values,
		as_dict=True,
	)
