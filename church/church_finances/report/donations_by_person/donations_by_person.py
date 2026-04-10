import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
	]
	cols.append({"fieldname": "total_amount", "fieldtype": "Currency", "label": "Total Amount", "width": 150})
	return cols


def get_data(filters=None):
	filters = filters or {}
	values = {}
	church_condition = get_church_condition(filters, "Collection", "`tabCollection`.`name`", values)

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
			`tabDonation`.person,
			SUM(`tabDonation`.amount) AS total_amount
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parenttype = 'Collection'
			AND `tabDonation`.person IS NOT NULL
			{date_condition}
			{church_condition}
		GROUP BY `tabDonation`.person
		ORDER BY total_amount DESC
		""",
		values,
		as_dict=True,
	)
