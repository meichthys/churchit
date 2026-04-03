import frappe

from church.utils import CHURCH_COLUMN, get_church_condition, set_report_link_titles, show_church_column


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = []
	if show_church_column(filters):
		cols.append(CHURCH_COLUMN)
	cols += [
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 200},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 300},
		{"fieldname": "creation", "fieldtype": "Datetime", "label": "Date", "width": 150},
	]
	return cols


def get_data(filters):
	filters = filters or {}
	values = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}
	church_condition = get_church_condition(filters, "cf.church", values)
	church_select = "cf.church, " if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT
			{church_select}cf.fund,
			ft.amount,
			ft.notes,
			ft.creation
		FROM `tabFund` cf
		INNER JOIN `tabFinancial Transaction` ft ON ft.parent = cf.name
		WHERE ft.parenttype = 'Fund'
			AND (%(from_date)s IS NULL OR DATE(ft.creation) >= %(from_date)s)
			AND (%(to_date)s IS NULL OR DATE(ft.creation) <= %(to_date)s)
			{church_condition}
		ORDER BY cf.fund, ft.creation DESC
		""",
		values,
		as_dict=True,
	)
