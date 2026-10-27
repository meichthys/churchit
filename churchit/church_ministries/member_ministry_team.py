# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A portal member's own ministry team assignments, blocks and calendar feed, and answers sent from a request email."""

import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, cint, format_time, get_url, getdate, now_datetime, nowdate, sbool

from churchit.church_ministries.doctype.function.function import TIME_FORMAT, get_time_window
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import ACCEPTED
from churchit.church_scope import session_person
from churchit.ics import calendar_response, make_calendar, make_event

# A calendar app drops an event the feed stops listing, so the feed keeps recent ones.
CALENDAR_HISTORY_DAYS = 90


def get_own_assignments(person: str, from_date: str | None = None) -> list[frappe._dict]:
	"""*person*'s assignments at functions that end on *from_date* (today by default) or later.

	Soonest first, each with its time and has_started.
	"""
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	Function = frappe.qb.DocType("Function")
	Position = frappe.qb.DocType("Ministry Team Position")
	# church-scope: the signed-in member's own assignments, by their person
	rows = (
		frappe.qb.from_(Assignment)
		.join(Function)
		.on(Assignment.function == Function.name)
		.join(Position)
		.on(Assignment.position == Position.name)
		.select(
			Assignment.name,
			Assignment.status,
			Assignment.decline_reason,
			Assignment.function,
			Assignment.modified,
			Function.modified.as_("function_modified"),
			Function.function_name,
			Function.start_date,
			Function.start_time,
			Function.end_date,
			Function.end_time,
			Function.all_day,
			Function.meeting_url,
			Position.title.as_("position"),
		)
		.where(
			(Assignment.person == person)
			& (Coalesce(Function.end_date, Function.start_date) >= (from_date or nowdate()))
		)
		.orderby(Function.start_date)
		.orderby(Function.start_time)
		.run(as_dict=True)
	)
	for row in rows:
		row.time = format_time(row.start_time, TIME_FORMAT) if row.start_time and not row.all_day else ""
		row.has_started = get_time_window(row)[0] <= now_datetime()
	return rows


def get_own_blocks(person: str) -> list[frappe._dict]:
	"""*person*'s blocks that have not ended yet, and repeating blocks that still repeat."""
	today = getdate()
	# church-scope: the signed-in member's own blocks, by their person
	blocks = frappe.get_all(
		"Ministry Team Block",
		filters={"person": person},
		or_filters={"to_date": (">=", today), "repeat_frequency": ("is", "set")},
		fields=[
			"name",
			"from_date",
			"to_date",
			"reason",
			"whole_household",
			"repeat_frequency",
			"repeat_until",
		],
		order_by="from_date asc",
	)
	return [
		block
		for block in blocks
		if block.to_date >= today or not block.repeat_until or block.repeat_until >= today
	]


def get_own_positions(person: str) -> list[frappe._dict]:
	"""The positions *person* can fill, each with the most times a month they serve in it."""
	# church-scope: the signed-in member's own roster rows, by their person
	rows = frappe.get_all(
		"Ministry Team Position Person",
		filters={"person": person, "parenttype": "Ministry Team Position", "parentfield": "people"},
		fields=["parent", "max_times_per_month"],
	)
	# church-scope: only the positions whose rosters name the signed-in member
	titles = dict(
		frappe.get_all(
			"Ministry Team Position",
			filters={"name": ("in", [row.parent for row in rows])},
			fields=["name", "title"],
			as_list=True,
		)
	)
	positions = [
		frappe._dict(
			position=row.parent, title=titles[row.parent], max_times_per_month=row.max_times_per_month
		)
		for row in rows
	]
	return sorted(positions, key=lambda row: row.title)


def get_calendar_links(person: str) -> frappe._dict | None:
	"""*person*'s calendar feed link, as https to copy and as webcal to open a calendar app."""
	key = frappe.db.get_value("Person", person, "team_calendar_key")
	if not key:
		return None
	url = get_url(f"/api/method/churchit.church_ministries.member_ministry_team.get_team_calendar?key={key}")
	return frappe._dict(url=url, webcal="webcal://" + url.partition("://")[2])


def get_calendar(person: str) -> str:
	"""*person*'s accepted assignments as an iCalendar feed."""
	events = []
	for row in get_own_assignments(person, add_days(nowdate(), -CALENDAR_HISTORY_DAYS)):
		if row.status != ACCEPTED:
			continue
		summary = _("{0} at {1}").format(row.position, row.function_name)
		stamp = max(row.modified, row.function_modified)
		events.append(make_event(row.name, row, summary, stamp, url=row.meeting_url))
	return make_calendar(_("Ministry Team"), events)


def get_assignment_by_key(key: str):
	"""The assignment a request email's link answers, or a refusal for any other key."""
	name = key and frappe.db.get_value("Ministry Team Assignment", {"response_key": key})
	if not name:
		frappe.throw(
			_("This link is not valid. Ask the church office for a new one."), frappe.PermissionError
		)
	return frappe.get_doc("Ministry Team Assignment", name)


def answer(assignment, status: str, reason: str | None):
	assignment.respond(status, reason)
	# Members cannot write an assignment. Each caller has checked whose answer this is.
	assignment.save(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def answer_own_assignment(assignment: str, status: str, reason: str | None = None):
	"""Accept or decline one of the signed-in member's own assignments."""
	doc = frappe.get_doc("Ministry Team Assignment", assignment)
	if not session_person() or doc.person != session_person():
		frappe.throw(_("This assignment is not yours to answer."), frappe.PermissionError)
	answer(doc, status, reason)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60)
def answer_by_key(key: str, status: str, reason: str | None = None):
	"""Accept or decline the assignment a request email's link points at, signed in or not."""
	answer(get_assignment_by_key(key), status, reason)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_team_calendar(key: str):
	"""The calendar feed a member's calendar link points at, for any calendar app that holds the link."""
	person = key and frappe.db.get_value("Person", {"team_calendar_key": key})
	if not person:
		frappe.throw(
			_("This calendar link is not valid. Make a new one on the Ministry Team page."),
			frappe.PermissionError,
		)

	return calendar_response(get_calendar(person), "ministry-team.ics")


@frappe.whitelist(methods=["POST"])
def make_own_calendar_key():
	"""Give the signed-in member a new calendar link. Their old link stops working."""
	person = session_person()
	if not person:
		frappe.throw(_("Your account is not linked to a member record."), frappe.PermissionError)
	frappe.db.set_value(
		"Person", person, "team_calendar_key", frappe.generate_hash(length=32), update_modified=False
	)


@frappe.whitelist(methods=["POST"])
def add_own_block(
	from_date: str,
	to_date: str,
	reason: str | None = None,
	whole_household: str | int = 0,
	repeat_frequency: str | None = None,
	repeat_until: str | None = None,
):
	"""Block the signed-in member from serving from *from_date* to *to_date*, once or repeating."""
	person = session_person()
	if not person:
		frappe.throw(_("Your account is not linked to a member record."), frappe.PermissionError)
	if getdate(to_date) < getdate():
		frappe.throw(_("Choose dates from today on."))

	frappe.get_doc(
		{
			"doctype": "Ministry Team Block",
			"person": person,
			"from_date": from_date,
			"to_date": to_date,
			"reason": reason,
			"whole_household": sbool(whole_household),
			"repeat_frequency": repeat_frequency,
			"repeat_until": repeat_until or None,
		}
	).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def remove_own_block(block: str):
	"""Remove one of the signed-in member's own blocks."""
	person = frappe.db.get_value("Ministry Team Block", block, "person")
	if not person or person != session_person():
		frappe.throw(_("This block is not yours to remove."), frappe.PermissionError)
	frappe.delete_doc("Ministry Team Block", block, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def set_own_frequency(position: str, max_times_per_month: str | int):
	"""Set the most times a month the signed-in member serves in *position*. 0 means no limit."""
	person = session_person()
	if not person:
		frappe.throw(_("Your account is not linked to a member record."), frappe.PermissionError)
	value = cint(max_times_per_month)
	if value < 0:
		frappe.throw(_("Choose 0 or more times a month."))

	position_doc = frappe.db.exists("Ministry Team Position", position) and frappe.get_doc(
		"Ministry Team Position", position, for_update=True
	)
	row = position_doc and next((row for row in position_doc.people if row.person == person), None)
	if not row:
		frappe.throw(_("You are not on this position."), frappe.PermissionError)

	row.max_times_per_month = value
	# Members cannot write a position. The member changes only their own roster row.
	position_doc.save(ignore_permissions=True)
