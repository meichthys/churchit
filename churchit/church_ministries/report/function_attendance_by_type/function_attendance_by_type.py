import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import today

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = filters or {}
	if filters.get("group"):
		frappe.has_permission("Group", doc=filters["group"], throw=True)
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "function",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 200,
		},
		{"fieldname": "group", "fieldtype": "Link", "label": _("Group"), "options": "Group", "width": 180},
		{"fieldname": "attendance_count", "fieldtype": "Int", "label": _("Attendance Count"), "width": 150},
	]


def get_data(filters=None):
	filters = filters or {}
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Function.name == Attendance.parent)
		.select(
			Attendance.parent.as_("function"),
			Function.group,
			Count(Attendance.person).as_("attendance_count"),
		)
		.where(Attendance.attendance_type.isin(COUNTED_TYPES) & (Function.start_date <= today()))
		.groupby(Attendance.parent, Function.group)
	)
	if filters.get("group"):
		query = query.where(Function.group == filters["group"])
	return scoped(query, Function, filters).run(as_dict=True)
