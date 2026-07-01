import frappe
from frappe.query_builder.functions import Count

from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "group_name", "fieldtype": "Data", "label": "Group", "width": 250},
		{"fieldname": "status", "fieldtype": "Data", "label": "Status", "width": 100},
		{"fieldname": "members", "fieldtype": "Int", "label": "Members", "width": 100},
		{"fieldname": "description", "fieldtype": "Data", "label": "Description", "width": 300},
	]


def get_data(filters=None):
	filters = filters or {}

	Group = frappe.qb.DocType("Group")
	GroupMember = frappe.qb.DocType("Group Member")

	query = (
		frappe.qb.from_(Group)
		.left_join(GroupMember)
		.on(GroupMember.parent == Group.name)
		.select(
			Group.name,
			Group.group_name,
			Group.status,
			Count(GroupMember.name).as_("members"),
			Group.description,
		)
		.groupby(Group.name)
		.orderby(Group.group_name)
	)

	if filters.get("status"):
		query = query.where(Group.status == filters["status"])
	if filters.get("from_date"):
		query = query.where(Group.creation >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(Group.creation <= filters["to_date"])

	return query.run(as_dict=True)
