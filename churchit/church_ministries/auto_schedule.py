# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill the open ministry team places of functions from each position's roster.

A greedy fill: people are asked in `availability.rank` order, and only people `availability.is_available`
passes are asked. A person serves in one position of a function. Each new assignment is Pending, and the
daily `send_team_emails` job sends the requests.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from churchit.church_ministries import availability
from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	ACCEPTED,
	PENDING,
)
from churchit.church_scope import church_query_filters, default_church, is_multi_church


@frappe.whitelist(methods=["POST"])
def fill_open_needs(function: str, ministry: str | None = None) -> frappe._dict:
	"""Ask people to fill the open places of *function*, and return the places assigned and still open.

	With *ministry*, only its positions are filled.
	"""
	frappe.has_permission("Function", doc=function, throw=True)
	frappe.has_permission("Ministry Team Assignment", "create", throw=True)
	if ministry:
		frappe.has_permission("Ministry", doc=ministry, throw=True)
	function_doc = lock_function(function)
	if get_time_window(function_doc)[0] <= now_datetime():
		frappe.throw(_("{0} has already started.").format(function_doc.title))

	result = frappe._dict(assigned=[], unfilled=[])
	fill_function(function_doc, result, ministry)
	return result


@frappe.whitelist(methods=["POST"])
def fill_open_needs_between(
	from_date: str, to_date: str, ministry: str | None = None, church: str | None = None
) -> frappe._dict:
	"""Fill the open places of the functions the user may read from *from_date* to *to_date* that have not started.

	With *ministry*, only its positions are filled. With *church*, only that church's functions and the
	shared ones are filled, as a report with that Church filter shows them.
	"""
	frappe.has_permission("Ministry Team Assignment", "create", throw=True)
	if ministry:
		frappe.has_permission("Ministry", doc=ministry, throw=True)
	functions = frappe.get_list(
		"Function",
		filters={
			"start_date": ("between", [max(getdate(from_date), getdate()), getdate(to_date)]),
			**church_query_filters({"church": church}),
		},
		order_by="start_date asc, name asc",
		pluck="name",
	)

	result = frappe._dict(assigned=[], unfilled=[])
	for function in functions:
		function_doc = lock_function(function)
		if get_time_window(function_doc)[0] > now_datetime():
			fill_function(function_doc, result, ministry)
	return result


def lock_function(function: str):
	"""Commit, then lock *function* and the people on the rosters it needs, before any plain read.

	Under REPEATABLE READ, a read made before the wait for a lock fixes an older snapshot. The commit
	also lets a range fill hold one Function lock at a time. The people locks make a fill of another
	function that may ask the same people wait for this one, so `availability.is_available` sees its
	requests.
	"""
	frappe.db.commit()
	function_doc = frappe.get_doc("Function", function, for_update=True)
	positions = [need.position for need in function_doc.team_needs]
	if not positions:
		return function_doc

	Roster = frappe.qb.DocType("Ministry Team Position Person")
	Person = frappe.qb.DocType("Person")
	# church-scope: locks only, the fill reads the rosters of the positions the function needs
	people = (
		frappe.qb.from_(Roster)
		.select(Roster.person)
		.where((Roster.parenttype == "Ministry Team Position") & Roster.parent.isin(positions))
		.for_update()
		.run(pluck=True)
	)
	if people:
		# The same order in every fill, so two fills never wait for each other's people.
		(
			frappe.qb.from_(Person)
			.select(Person.name)
			.where(Person.name.isin(people))
			.orderby(Person.name)
			.for_update()
			.run()
		)
	return function_doc


def fill_function(function_doc, result: frappe._dict, ministry: str | None = None):
	"""Fill each position *function_doc* needs, adding to *result*. The caller has locked the function.

	The assignments are a locking read, as in `get_seats_taken`, so they include rows committed while
	this request waited for the lock.
	"""
	# An assignment takes the function's church, or on a shared function the user's default church, and
	# refuse_another_churches_record refuses a position of any other church.
	assignment_church = function_doc.church or default_church()
	needed = defaultdict(int)
	for need in function_doc.team_needs:
		church, position_ministry = frappe.get_cached_value(
			"Ministry Team Position", need.position, ["church", "ministry"]
		)
		is_usable = not is_multi_church() or church in ("", None, assignment_church)
		if is_usable and (not ministry or ministry == position_ministry):
			needed[need.position] += need.quantity

	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	# church-scope: the assignments of the one function the caller may read and has locked
	assignments = (
		frappe.qb.from_(Assignment)
		.select(Assignment.position, Assignment.person, Assignment.status)
		.where(Assignment.function == function_doc.name)
		.for_update()
		.run(as_dict=True)
	)
	window = get_time_window(function_doc)
	for position, quantity in needed.items():
		asked = [row for row in assignments if row.position == position]
		open_places = quantity - sum(1 for row in asked if row.status in (PENDING, ACCEPTED))
		if open_places > 0:
			fill_position(
				function_doc.name, position, open_places, {row.person for row in asked}, window, result
			)


def fill_position(function: str, position: str, open_places: int, asked: set, window: tuple, result):
	"""Ask the best ranked people of the roster who were never asked for this place and can serve."""
	roster = frappe.get_cached_doc("Ministry Team Position", position).people
	for person in availability.rank([row.person for row in roster if row.person not in asked]):
		if not open_places:
			break
		if availability.is_available(person, *window, position):
			result.assigned.append(assign(function, position, person))
			open_places -= 1
	if open_places:
		result.unfilled.append(frappe._dict(function=function, position=position, open=open_places))


def assign(function: str, position: str, person: str) -> frappe._dict:
	"""Insert one Pending assignment with the user's own rights, so the church guards run."""
	assignment = frappe.get_doc(
		{
			"doctype": "Ministry Team Assignment",
			"function": function,
			"position": position,
			"person": person,
			"status": PENDING,
		}
	).insert()
	return frappe._dict(
		assignment=assignment.name,
		function=function,
		position=position,
		person=person,
		person_name=assignment.person_name,
	)
