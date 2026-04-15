import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "type", "fieldtype": "Data", "label": "Type", "width": 200},
		{"fieldname": "counts", "fieldtype": "Int", "label": "Count", "width": 100},
	]


def get_data(filters):
	filters = filters or {}
	values = {
		"start": filters.get("start"),
		"end": filters.get("end"),
	}

	return frappe.db.sql(
		"""
		SELECT type as type, count(name) as counts
		FROM `tabFunction`
		WHERE (start_date IS NULL OR end_date IS NULL OR date(start_date) BETWEEN %(start)s AND %(end)s)
		GROUP BY type
		""",
		values,
		as_dict=True,
	)
