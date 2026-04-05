import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "ministry_name", "fieldtype": "Data", "label": "Ministry", "width": 200},
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 150},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "group", "fieldtype": "Link", "label": "Group", "options": "Group", "width": 150},
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 150},
		{"fieldname": "publish", "fieldtype": "Check", "label": "Published", "width": 100},
		{"fieldname": "description", "fieldtype": "Data", "label": "Description", "width": 300},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = ""
	values = {}

	conditions += get_church_condition(filters, "`tabMinistry`.church", values)

	if filters.get("status"):
		conditions += " AND `tabMinistry`.status = %(status)s"
		values["status"] = filters["status"]

	if filters.get("from_date"):
		conditions += " AND `tabMinistry`.start_date >= %(from_date)s"
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND `tabMinistry`.start_date <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	if filters.get("fund"):
		conditions += " AND `tabMinistry`.fund = %(fund)s"
		values["fund"] = filters["fund"]

	if filters.get("publish") == "Yes":
		conditions += " AND `tabMinistry`.publish = 1"
	elif filters.get("publish") == "No":
		conditions += " AND `tabMinistry`.publish = 0"

	return frappe.db.sql(
		f"""
		SELECT
			`tabMinistry`.name,
			`tabMinistry`.ministry_name,
			`tabMinistry`.church,
			`tabMinistry`.status,
			`tabMinistry`.start_date,
			`tabMinistry`.end_date,
			`tabMinistry`.`group`,
			`tabMinistry`.fund,
			`tabMinistry`.publish,
			`tabMinistry`.description
		FROM `tabMinistry`
		WHERE 1=1
			{conditions}
		ORDER BY `tabMinistry`.ministry_name
		""",
		values,
		as_dict=True,
	)
