import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Sign Up", "options": "Function Sign-Up", "width": 120},
		{"fieldname": "function", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 180},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 180},
		{"fieldname": "item", "fieldtype": "Link", "label": "Item", "options": "Sign Up Item", "width": 150},
		{"fieldname": "description", "fieldtype": "Small Text", "label": "Description", "width": 250},
		{"fieldname": "quantity_needed", "fieldtype": "Int", "label": "Qty Needed", "width": 100},
		{"fieldname": "quantity_signed_up", "fieldtype": "Int", "label": "Qty Signed Up", "width": 100},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = ["1=1"]

	if filters.get("function"):
		conditions.append(f"fsu.function = '{frappe.db.escape(filters['function'])}'")

	if filters.get("item"):
		conditions.append(f"fsui.item = '{frappe.db.escape(filters['item'])}'")

	if filters.get("person"):
		conditions.append(f"fsu.person = '{frappe.db.escape(filters['person'])}'")

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
		SELECT
			fsu.name,
			fsu.function,
			fsu.person,
			fsui.item,
			fsui.small_text_lwph AS description,
			fsui.quantity_needed,
			fsui.quantity_signed_up
		FROM `tabFunction Sign-Up` fsu
		INNER JOIN `tabFunction Sign-Up Item` fsui ON fsu.name = fsui.parent
		WHERE {where_clause}
		ORDER BY fsu.function, fsu.person, fsui.item
		""",
		as_dict=True,
	)
