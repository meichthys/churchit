import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "user", "fieldtype": "Link", "label": "User", "options": "User", "width": 200},
		{
			"fieldname": "bible_reference",
			"fieldtype": "Link",
			"label": "Reference",
			"options": "Bible Reference",
			"width": 240,
		},
		{"fieldname": "progress", "fieldtype": "Percent", "label": "Progress", "width": 100},
		{"fieldname": "memorized", "fieldtype": "Check", "label": "Memorized", "width": 100},
		{"fieldname": "memorized_on", "fieldtype": "Date", "label": "Memorized On", "width": 120},
		{
			"fieldname": "times_memorized",
			"fieldtype": "Int",
			"label": "Perfect Runs",
			"width": 110,
		},
	]


def get_data(filters):
	conditions = {}
	memorized = filters.get("memorized")
	if memorized in (1, "1", True, "Yes"):
		conditions["memorized"] = 1
	elif memorized in (0, "0", False, "No"):
		conditions["memorized"] = 0
	if filters.get("user"):
		conditions["user"] = filters["user"]

	return frappe.get_all(
		"Bible Memory Item",
		filters=conditions,
		fields=[
			"name",
			"user",
			"bible_reference",
			"progress",
			"memorized",
			"memorized_on",
			"times_memorized",
		],
		order_by="memorized desc, memorized_on desc, modified desc",
	)
