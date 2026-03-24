import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, show_church_column


def execute(filters=None):
	return get_columns(filters), get_data(filters)


def get_columns(filters=None):
	cols = [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols.append({"fieldname": "total_amount", "fieldtype": "Currency", "label": "Total Amount", "width": 150})
	return cols


def get_data(filters=None):
	filters = filters or {}
	values = {}
	church_condition = get_church_condition(filters, "`tabCollection`.church", values)
	church_select = ", `tabCollection`.church" if show_church_column(filters) else ""
	church_group = ", `tabCollection`.church" if show_church_column(filters) else ""

	date_condition = ""
	if filters.get("from_date"):
		date_condition += " AND `tabCollection`.date >= %(from_date)s"
		values["from_date"] = filters["from_date"]
	if filters.get("to_date"):
		date_condition += " AND `tabCollection`.date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	return frappe.db.sql(
		f"""
		SELECT
			`tabDonation`.person{church_select},
			SUM(`tabDonation`.amount) AS total_amount
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parenttype = 'Collection'
			AND `tabDonation`.person IS NOT NULL
			{date_condition}
			{church_condition}
		GROUP BY `tabDonation`.person{church_group}
		ORDER BY total_amount DESC
		""",
		values,
		as_dict=True,
	)
