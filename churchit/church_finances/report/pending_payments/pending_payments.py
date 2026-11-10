import frappe


def execute(filters=None):
	columns = [
		{
			"label": "Missionary Payment",
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Missionary Payment",
			"width": 140,
		},
		{
			"label": "Missionary",
			"fieldname": "missionary",
			"fieldtype": "Link",
			"options": "Missionary",
			"width": 160,
		},
		{"label": "Fund", "fieldname": "fund", "fieldtype": "Link", "options": "Fund", "width": 160},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": "Status", "fieldname": "status", "fieldtype": "Select", "width": 110},
		{"label": "Payment Date", "fieldname": "payment_date", "fieldtype": "Date", "width": 120},
	]

	conditions = ["status in ('Scheduled', 'Approved')"]
	values = {}

	if filters:
		if filters.get("missionary"):
			conditions.append("missionary = %(missionary)s")
			values["missionary"] = filters["missionary"]

	where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

	data = frappe.db.sql(
		f"""
		SELECT name, missionary, fund, amount, status, payment_date
		from `tabMissionary Payment`
		{where_clause}
		ORDER BY payment_date ASC
		""",
		values,
		as_dict=True,
	)

	return columns, data
