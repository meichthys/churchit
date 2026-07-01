import frappe

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters or {})
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Function", "options": "Function", "width": 200},
		{"fieldname": "function_name", "fieldtype": "Data", "label": "Name", "width": 200},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Function Type", "width": 180},
		{
			"fieldname": "associated_ministry",
			"fieldtype": "Link",
			"label": "Ministry",
			"options": "Ministry",
			"width": 180,
		},
		{"fieldname": "repeat_frequency", "fieldtype": "Data", "label": "Frequency", "width": 110},
		{"fieldname": "repeat_schedule", "fieldtype": "Data", "label": "Repeats On", "width": 140},
		{"fieldname": "repeat_until", "fieldtype": "Date", "label": "Repeat Until", "width": 120},
	]


def get_data(filters):
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Function)
		.select(
			Function.name,
			Function.function_name,
			Function.type,
			Function.associated_ministry,
			Function.repeat_frequency,
			Function.repeat_day_of_week,
			Function.repeat_month_day,
			Function.repeat_until,
		)
		.where(Function.auto_repeat == 1)
		.orderby(Function.associated_ministry)
		.orderby(Function.function_name)
	)

	if filters.get("associated_ministry"):
		query = query.where(Function.associated_ministry == filters["associated_ministry"])
	if filters.get("repeat_frequency"):
		query = query.where(Function.repeat_frequency == filters["repeat_frequency"])

	rows = query.run(as_dict=True)

	for row in rows:
		if row["repeat_frequency"] == "Weekly":
			row["repeat_schedule"] = row.get("repeat_day_of_week") or ""
		elif row["repeat_frequency"] == "Monthly":
			day = row.get("repeat_month_day")
			row["repeat_schedule"] = f"Day {day}" if day else ""
		else:
			row["repeat_schedule"] = ""
	return rows
