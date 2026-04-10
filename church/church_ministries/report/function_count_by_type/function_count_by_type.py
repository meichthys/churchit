import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns(filters=None):
	cols = []
	cols += [
		{"fieldname": "type", "fieldtype": "Data", "label": "Type", "width": 200},
		{"fieldname": "counts", "fieldtype": "Int", "label": "Count", "width": 100},
	]
	return cols


def get_data(filters):
	filters = filters or {}
	conditions = ""
	values = {
		"start": filters.get("start"),
		"end": filters.get("end"),
	}

	conditions += get_church_condition(filters, "Function", "`tabFunction`.`name`", values)

	return frappe.db.sql(
		f"""
		SELECT type as type, count(name) as counts
		FROM `tabFunction`
		WHERE (start_date IS NULL OR end_date IS NULL OR date(start_date) BETWEEN %(start)s AND %(end)s)
			{conditions}
		GROUP BY type
		""",
		values,
		as_dict=True,
	)
