import frappe

from church.utils import get_church_condition


def execute(filters=None):
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Data", "label": "Fund", "width": 200},
		{"fieldname": "amount", "fieldtype": "Currency", "label": "Amount", "width": 120},
		{"fieldname": "notes", "fieldtype": "Data", "label": "Notes", "width": 300},
		{"fieldname": "creation", "fieldtype": "Datetime", "label": "Date", "width": 150},
	]


def get_data(filters):
	filters = filters or {}
	values = {
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
	}
	church_condition = get_church_condition(filters, "cf.church", values)

	return frappe.db.sql(
		f"""
		SELECT
			cf.fund,
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
