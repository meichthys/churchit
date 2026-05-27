import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "ministry_name", "fieldtype": "Data", "label": "Ministry", "width": 200},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "start_date", "fieldtype": "Date", "label": "Start Date", "width": 120},
		{"fieldname": "end_date", "fieldtype": "Date", "label": "End Date", "width": 120},
		{"fieldname": "group", "fieldtype": "Link", "label": "Group", "options": "Group", "width": 150},
		{"fieldname": "publish", "fieldtype": "Check", "label": "Published", "width": 100},
		{"fieldname": "description", "fieldtype": "Data", "label": "Description", "width": 300},
	]


def get_data(filters=None):
	filters = filters or {}

	Ministry = frappe.qb.DocType("Ministry")

	query = (
		frappe.qb.from_(Ministry)
		.select(
			Ministry.name,
			Ministry.ministry_name,
			Ministry.status,
			Ministry.start_date,
			Ministry.end_date,
			Ministry["group"],
			Ministry.publish,
			Ministry.description,
		)
		.orderby(Ministry.ministry_name)
	)

	if filters.get("status"):
		query = query.where(Ministry.status == filters["status"])
	if filters.get("from_date"):
		query = query.where(Ministry.start_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Ministry.start_date <= filters["to_date"])
	if filters.get("publish") == "Yes":
		query = query.where(Ministry.publish == 1)
	elif filters.get("publish") == "No":
		query = query.where(Ministry.publish == 0)

	return query.run(as_dict=True)
