import frappe

from church.utils import set_report_link_titles


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
	conditions = ["auto_repeat = 1"]
	values = {}
	if filters.get("associated_ministry"):
		conditions.append("associated_ministry = %(associated_ministry)s")
		values["associated_ministry"] = filters["associated_ministry"]
	if filters.get("repeat_frequency"):
		conditions.append("repeat_frequency = %(repeat_frequency)s")
		values["repeat_frequency"] = filters["repeat_frequency"]

	rows = frappe.db.sql(
		f"""
		SELECT name, function_name, type, associated_ministry,
		       repeat_frequency, repeat_day_of_week, repeat_month_day, repeat_until
		FROM `tabFunction`
		WHERE {" AND ".join(conditions)}
		ORDER BY associated_ministry, function_name
		""",
		values,
		as_dict=True,
	)

	for row in rows:
		if row["repeat_frequency"] == "Weekly":
			row["repeat_schedule"] = row.get("repeat_day_of_week") or ""
		elif row["repeat_frequency"] == "Monthly":
			day = row.get("repeat_month_day")
			row["repeat_schedule"] = f"Day {day}" if day else ""
		else:
			row["repeat_schedule"] = ""
	return rows
