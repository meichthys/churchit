import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "sign_up_display",
			"fieldtype": "HTML",
			"label": "Sign Up",
			"width": 250,
		},
		{
			"fieldname": "function_display",
			"fieldtype": "HTML",
			"label": "Function",
			"width": 200,
		},
		{"fieldname": "item", "fieldtype": "Link", "label": "Item", "options": "Sign-Up Item", "width": 200},
		{
			"fieldname": "person_display",
			"fieldtype": "HTML",
			"label": "Person",
			"width": 250,
		},
		{"fieldname": "my_quantity", "fieldtype": "Int", "label": "Quantity", "width": 100},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = []
	params = {}

	if filters.get("function"):
		conditions.append("fsu.function = %(function)s")
		params["function"] = filters["function"]

	if filters.get("item"):
		conditions.append("fsui.item = %(item)s")
		params["item"] = filters["item"]

	if filters.get("person"):
		conditions.append("fsu.person = %(person)s")
		params["person"] = filters["person"]

	where_clause = " AND ".join(conditions) if conditions else "1=1"

	rows = frappe.db.sql(
		f"""
		SELECT
			fsu.name,
			fsu.title,
			fsu.function,
			f.function_name,
			fsui.item,
			fsu.person,
			p.full_name,
			fsui.my_quantity
		FROM `tabFunction Sign-Up` fsu
		INNER JOIN `tabFunction Sign-Up Item` fsui ON fsu.name = fsui.parent
		INNER JOIN `tabFunction` f ON fsu.function = f.name
		INNER JOIN `tabPerson` p ON fsu.person = p.name
		WHERE {where_clause}
		ORDER BY fsu.name, fsu.function, fsui.item
		""",
		params,
		as_dict=True,
	)

	# Format as clickable links with titles
	for row in rows:
		row["sign_up_display"] = f'<a href="/app/function-sign-up/{row["name"]}">{row["title"]}</a>'
		row["function_display"] = f'<a href="/app/function/{row["function"]}">{row["function_name"]}</a>'
		row["person_display"] = f'<a href="/app/person/{row["person"]}">{row["full_name"]}</a>'

	return rows
