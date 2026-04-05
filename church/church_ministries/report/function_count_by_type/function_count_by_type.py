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

	conditions += get_church_condition(filters, "church", values)
	church_select = "church, " if show_church_column(filters) else ""
	church_group = "church, " if show_church_column(filters) else ""

	return frappe.db.sql(
		f"""
		SELECT {church_select}type as type, count(name) as counts
		FROM `tabFunction`
		WHERE (start_date IS NULL OR end_date IS NULL OR date(start_date) BETWEEN %(start)s AND %(end)s)
			{conditions}
		GROUP BY {church_group}type
		""",
		values,
		as_dict=True,
	)
