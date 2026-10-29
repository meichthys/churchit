# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import format_date

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	ACCEPTED,
	PENDING,
)
from churchit.church_ministries.report.ministry_team_schedule.ministry_team_schedule import (
	get_assignments,
	get_needs,
)
from churchit.utils import set_report_link_titles

MAX_COLUMNS = 60


def execute(filters=None):
	filters = frappe._dict(filters or {})
	needs, assignments = get_needs(filters), get_assignments(filters)
	functions = get_functions(needs + assignments)
	message = None
	if len(functions) > MAX_COLUMNS:
		message = _(
			"The range has {0} functions. The grid shows the first {1}. Choose a shorter range."
		).format(len(functions), MAX_COLUMNS)
		functions = functions[:MAX_COLUMNS]

	columns = get_columns(functions)
	data = get_data(functions, needs, assignments)
	set_report_link_titles(columns, data)
	return columns, data, message


def get_functions(rows: list[frappe._dict]) -> list[frappe._dict]:
	"""The functions the needs and assignments are at, soonest first."""
	starts = {row.function: (row.start_date, row.start_time or timedelta()) for row in rows}
	names = sorted(starts, key=lambda name: (*starts[name], name))
	# church-scope: titles of the functions the scoped needs and assignments already chose
	titles = (
		dict(frappe.db.get_values("Function", {"name": ("in", names)}, ["name", "title"])) if names else {}
	)
	return [frappe._dict(name=name, title=titles[name], start_date=starts[name][0]) for name in names]


def get_columns(functions: list[frappe._dict]) -> list[dict]:
	columns = [
		{
			"fieldname": "ministry",
			"fieldtype": "Link",
			"label": _("Ministry"),
			"options": "Ministry",
			"width": 160,
		},
		{
			"fieldname": "position",
			"fieldtype": "Link",
			"label": _("Position"),
			"options": "Ministry Team Position",
			"width": 180,
		},
	]
	return columns + [
		{
			"fieldname": frappe.scrub(function.name),
			"fieldtype": "Data",
			"label": f"{format_date(function.start_date)} {function.title}",
			"width": 220,
		}
		for function in functions
	]


def get_data(functions, needs, assignments) -> list[frappe._dict]:
	"""One row per position, grouped by ministry, with a cell for each function it serves at.

	Each cell's text gives the open places and the people asked. `_cells` holds the same for the formatter.
	"""
	fieldnames = {function.name: frappe.scrub(function.name) for function in functions}
	rows = {}
	for need in needs:
		if need.function in fieldnames:
			get_cell(rows, need, fieldnames).needed += need.quantity
	for assignment in assignments:
		if assignment.function in fieldnames:
			cell = get_cell(rows, assignment, fieldnames)
			cell.people.append({"name": assignment.person_name, "status": assignment.status})
			cell.filling += assignment.status in (ACCEPTED, PENDING)

	for row in rows.values():
		for fieldname, cell in row._cells.items():
			cell.open = max(cell.pop("needed") - cell.pop("filling"), 0)
			row[fieldname] = ", ".join(
				([_("{0} open").format(cell.open)] if cell.open else [])
				+ [f"{person['name']} ({_(person['status'])})" for person in cell.people]
			)
	return sorted(rows.values(), key=lambda row: (row.ministry_name, row.position_name, row.position))


def get_cell(rows: dict, source: frappe._dict, fieldnames: dict) -> frappe._dict:
	row = rows.get(source.position)
	if not row:
		ministry, position_name = frappe.get_cached_value(
			"Ministry Team Position", source.position, ["ministry", "position_name"]
		)
		row = rows[source.position] = frappe._dict(
			ministry=ministry,
			ministry_name=frappe.get_cached_value("Ministry", ministry, "ministry_name"),
			position=source.position,
			position_name=position_name,
			_cells={},
		)
	return row._cells.setdefault(
		fieldnames[source.function], frappe._dict(function=source.function, needed=0, filling=0, people=[])
	)
