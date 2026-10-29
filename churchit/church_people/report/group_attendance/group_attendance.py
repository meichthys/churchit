# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_days, flt, getdate, today

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles

DEFAULT_WEEKS = 12


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.group:
		frappe.has_permission("Group", doc=filters.group, throw=True)
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "group", "fieldtype": "Link", "label": _("Group"), "options": "Group", "width": 220},
		{
			"fieldname": "group_type",
			"fieldtype": "Link",
			"label": _("Group Type"),
			"options": "Group Type",
			"width": 150,
		},
		{"fieldname": "meetings_held", "fieldtype": "Int", "label": _("Meetings Held"), "width": 130},
		{
			"fieldname": "average_attendance",
			"fieldtype": "Float",
			"label": _("Average Attended"),
			"precision": 1,
			"width": 140,
		},
		{"fieldname": "members", "fieldtype": "Int", "label": _("Current Members"), "width": 140},
		{"fieldname": "attendance_rate", "fieldtype": "Percent", "label": _("Attendance Rate"), "width": 140},
	]


def get_data(filters):
	"""One row per group that held a meeting in the range, with its counted attendance."""
	rows = get_query(filters).run(as_dict=True)
	for row in rows:
		row.average_attendance = flt(row.attended / row.meetings_held, 1)
		row.attendance_rate = flt(100 * row.average_attendance / row.members, 1) if row.members else None
		del row["attended"]
	return rows


def get_query(filters):
	"""Held meetings: past, not marked Did Not Meet, and not a group's schedule template."""
	from_date = filters.from_date or add_days(today(), -7 * DEFAULT_WEEKS)
	to_date = min(getdate(filters.to_date or today()), getdate())
	Function = frappe.qb.DocType("Function")
	Attendance = frappe.qb.DocType("Function Attendance")
	Group = frappe.qb.DocType("Group")
	Member = frappe.qb.DocType("Group Member")
	members = (
		frappe.qb.from_(Member)
		.select(Count(Member.name))
		.where((Member.parenttype == "Group") & (Member.parent == Group.name))
	)

	query = (
		frappe.qb.from_(Function)
		.join(Group)
		.on(Group.name == Function.group)
		.left_join(Attendance)
		.on(
			(Attendance.parenttype == "Function")
			& (Attendance.parent == Function.name)
			& Attendance.attendance_type.isin(COUNTED_TYPES)
		)
		.select(
			Group.name.as_("group"),
			Group.group_type,
			Count(Function.name).distinct().as_("meetings_held"),
			Count(Attendance.person).as_("attended"),
			members.as_("members"),
		)
		.where(
			Function.start_date[from_date:to_date]
			& (Function.did_not_meet == 0)
			& (Function.auto_repeat == 0)
		)
		.groupby(Group.name, Group.group_name, Group.group_type)
		.orderby(Group.group_name)
	)
	if filters.group:
		query = query.where(Function.group == filters.group)
	if filters.group_type:
		query = query.where(Group.group_type == filters.group_type)
	return scoped(scoped(query, Function, filters), Group, filters)
