import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, set_report_link_titles, show_church_column


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = [
		{"fieldname": "collection", "fieldtype": "Link", "label": "Collection", "options": "Collection", "width": 180},
	]
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols += [
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 150},
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 150},
		{"fieldname": "payment_type", "fieldtype": "Data", "label": "Payment Type", "width": 120},
		{"fieldname": "check_number", "fieldtype": "Data", "label": "Check #", "width": 100},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 200},
	]
	return cols


def get_data(filters):
	filters = filters or {}
	values = {"parent_filter": filters.get("parent_filter")}
	church_condition = get_church_condition(filters, "`tabCollection`.church", values)
	church_select = ", `tabCollection`.church" if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT
			`tabDonation`.parent as collection{church_select},
			`tabDonation`.fund,
			`tabDonation`.person,
			`tabDonation`.payment_type,
			`tabDonation`.check_number,
			sum(`tabDonation`.amount) as amount,
			`tabDonation`.notes
		FROM `tabDonation`
		INNER JOIN `tabCollection` ON `tabCollection`.name = `tabDonation`.parent
		WHERE `tabDonation`.parent = %(parent_filter)s
			{church_condition}
		GROUP BY check_number
		""",
		values,
		as_dict=True,
	)
