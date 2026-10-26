# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A portal member's own ministry team assignments, blocks and calendar feed, and answers sent from a request email."""

import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.rate_limiter import rate_limit
from frappe.utils import add_days, format_time, get_url, getdate, now_datetime, nowdate, sbool

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
	"""*person*'s blocks that have not ended yet."""
	# church-scope: the signed-in member's own blocks, by their person
	return frappe.get_all(
		"Ministry Team Block",
		filters={"person": person, "to_date": (">=", nowdate())},
		fields=["name", "from_date", "to_date", "reason", "whole_household"],
		order_by="from_date asc",
	)


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
def add_own_block(from_date: str, to_date: str, reason: str | None = None, whole_household: str | int = 0):
	"""Block the signed-in member from serving from *from_date* to *to_date*."""
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
		}
	).insert(ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def remove_own_block(block: str):
	"""Remove one of the signed-in member's own blocks."""
	person = frappe.db.get_value("Ministry Team Block", block, "person")
	if not person or person != session_person():
		frappe.throw(_("This block is not yours to remove."), frappe.PermissionError)
	frappe.delete_doc("Ministry Team Block", block, ignore_permissions=True)
