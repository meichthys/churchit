import frappe

from church.utils import get_church_condition, set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "group_name", "fieldtype": "Data", "label": "Group", "width": 250},
		{"fieldname": "church", "fieldtype": "Link", "label": "Church", "options": "Church", "width": 150},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "members", "fieldtype": "Int", "label": "Members", "width": 100},
		{"fieldname": "description", "fieldtype": "Data", "label": "Description", "width": 300},
	]


def get_data(filters=None):
	filters = filters or {}
	conditions = ""
	values = {}

	conditions += get_church_condition(filters, "`tabGroup`.church", values)

	if filters.get("status"):
		conditions += " AND `tabGroup`.status = %(status)s"
		values["status"] = filters["status"]

	if filters.get("from_date"):
		conditions += " AND `tabGroup`.creation >= %(from_date)s"
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions += " AND `tabGroup`.creation <= %(to_date)s"
		values["to_date"] = filters["to_date"]

	return frappe.db.sql(
		f"""
		SELECT
			`tabGroup`.name,
			`tabGroup`.group_name,
			`tabGroup`.church,
			`tabGroup`.status,
			COUNT(`tabGroup Member`.name) as members,
			`tabGroup`.description
		FROM `tabGroup`
		LEFT JOIN `tabGroup Member` ON `tabGroup Member`.parent = `tabGroup`.name
		WHERE `tabGroup`.is_group = 0
			{conditions}
		GROUP BY `tabGroup`.name
		ORDER BY `tabGroup`.group_name
		""",
		values,
		as_dict=True,
	)
