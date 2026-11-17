# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import timedelta

import frappe
from frappe import _

from churchit.church_scope import get_church_columns, scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "start_date", "fieldtype": "Date", "label": _("Date"), "width": 110},
		{
			"fieldname": "function",
			"fieldtype": "Link",
			"label": _("Function"),
			"options": "Function",
			"width": 220,
		},
		{
			"fieldname": "position",
			"fieldtype": "Link",
			"label": _("Position"),
			"options": "Ministry Team Position",
			"width": 220,
		},
		{"fieldname": "needed", "fieldtype": "Int", "label": _("Needed"), "width": 90},
		{"fieldname": "accepted", "fieldtype": "Int", "label": _("Accepted"), "width": 90},
		{"fieldname": "pending", "fieldtype": "Int", "label": _("Pending"), "width": 90},
		{"fieldname": "open", "fieldtype": "Int", "label": _("Open"), "width": 80},
		{"fieldname": "people", "fieldtype": "Data", "label": _("People"), "width": 360},
	]


def get_data(filters):
	"""One row per function and position: what it needs, who is asked, and how many places are open."""
	rows = {}
	for need in get_needs(filters):
		row = rows.setdefault((need.function, need.position), new_row(need))
		row.needed += need.quantity

	for assignment in get_assignments(filters):
		row = rows.setdefault((assignment.function, assignment.position), new_row(assignment))
		row.people.append(f"{assignment.person_name} ({_(assignment.status)})")
		if assignment.status == "Accepted":
			row.accepted += 1
		elif assignment.status == "Pending":
			row.pending += 1

	data = sorted(rows.values(), key=lambda row: (row.start_date, row.start_time, row.function, row.position))
	for row in data:
		row.open = max(row.needed - row.accepted - row.pending, 0)
		row.people = ", ".join(row.people)
	return [row for row in data if row.open or not filters.only_open]


def new_row(source):
	return frappe._dict(
		church=source.church,
		start_date=source.start_date,
		start_time=source.start_time or timedelta(),
		function=source.function,
		position=source.position,
		needed=0,
		accepted=0,
		pending=0,
		people=[],
	)


def get_needs(filters):
	Need = frappe.qb.DocType("Function Team Need")
	query = frappe.qb.from_(Need).select(Need.parent.as_("function"), Need.position, Need.quantity)
	return run_for_functions(query, Need, Need.parent, filters)


def get_assignments(filters):
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	query = (
		frappe.qb.from_(Assignment)
		.select(Assignment.function, Assignment.position, Assignment.person_name, Assignment.status)
		.orderby(Assignment.person_name)
	)
	return run_for_functions(query, Assignment, Assignment.function, filters)


def run_for_functions(query, table, function_field, filters):
	"""Run *query* over the functions and positions *filters* pick, joined to their Function."""
	Function = frappe.qb.DocType("Function")
	Position = frappe.qb.DocType("Ministry Team Position")
	query = (
		query.join(Function)
		.on(function_field == Function.name)
		.join(Position)
		.on(table.position == Position.name)
		.select(Function.start_date, Function.start_time, Function.church)
	)
	if filters.function:
		query = query.where(Function.name == filters.function)
	else:
		query = query.where(Function.start_date[filters.from_date : filters.to_date])
	if filters.ministry:
		query = query.where(Position.ministry == filters.ministry)
	return scoped(query, Function, filters).run(as_dict=True)
