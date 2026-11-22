# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member app's home: the member's week, what needs an answer, and the church's notices."""

from collections.abc import Callable

import frappe
from frappe.model import get_permitted_fields
from frappe.utils import add_days, cint, format_time, formatdate, getdate, today
from frappe.utils.html_utils import sanitize_html

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	DECLINED,
	PENDING,
)
from churchit.church_ministries.member_attendance import get_upcoming_sign_ups
from churchit.church_ministries.member_ministry_team import get_own_assignments
from churchit.church_ministries.pre_check_in import get_functions
from churchit.church_prayers.prayer_access import get_community_filters, get_open_request_filters
from churchit.church_scope import church_filters, church_query_filters
from churchit.church_website.pages import (
	can_open_members_only_pages,
	get_hidden_pages,
	get_members_only_pages,
	is_page_off,
)
from churchit.portal.access import require_page, require_person
from churchit.portal.groups import get_portal_groups
from churchit.portal.household import get_check_in_people, get_member_rows
from churchit.utils import LONG_DATE_FORMAT

WEEK_DAYS = 7
LOOK_AHEAD_DAYS = 60
LOOK_AHEAD_ROWS = 5
NOTICE_BULLETINS = 2
PRAYER_REQUESTS = 2


@frappe.whitelist(methods=["GET"])
def get_home() -> dict:
	"""The signed-in member's week, requests that need an answer, check-in, and the church's notices. Reads only."""
	person = require_person()

	is_on = get_switches()
	entries = get_entries(person, is_on)
	week_end = add_days(today(), WEEK_DAYS - 1)
	this_week = [entry for entry in entries if entry["date"] <= week_end]
	later = [entry for entry in entries if entry["date"] > week_end][:LOOK_AHEAD_ROWS]

	return {
		"person": person,
		"check_in": get_check_in(person),
		"needs_answer": get_requests_to_answer(person) if is_on("ministry-team") else [],
		"week": group_by_day(this_week),
		"ahead": [format_entry(entry) for entry in later],
		"notices": get_notices() if is_on("announcements") else [],
		"bulletin": get_newest_bulletin() if is_on("bulletins") else None,
		"members_only_pages": get_members_pages(),
		"prayer_requests": get_prayer_requests() if is_on("community-prayer-requests") else [],
	}


def get_switches() -> Callable[[str], bool]:
	"""A function that tells whether a page is on for the member, from one read of the hidden pages."""
	hidden = get_hidden_pages()
	return lambda page: not is_page_off(page, hidden)


def get_entries(person: str, is_on: Callable[[str], bool]) -> list[dict]:
	"""The member's sign-ups, accepted serving and group meetings from today on, soonest first.

	An entry links to its page only while that page is on. Serving is left out while ministry-team is off.
	"""
	entries = get_sign_up_entries(person) + get_group_entries(person)
	if is_on("ministry-team"):
		entries += get_serving_entries(person)
	for entry in entries:
		if entry["route"] and not is_on(entry["route"]):
			entry["route"] = None
	last_day = add_days(today(), LOOK_AHEAD_DAYS)
	entries = [entry for entry in entries if entry["date"] <= last_day]
	return sorted(entries, key=lambda entry: (entry["date"], entry["time"] or ""))


def get_sign_up_entries(person: str) -> list[dict]:
	"""A Function Sign-Up of the member, with its Function's start time."""
	functions = get_upcoming_sign_ups(person, include_today=True)
	# church-scope: the Functions of the member's own sign-ups, by name
	times = dict(
		frappe.get_all(
			"Function",
			filters={"name": ("in", [function.name for function in functions] or [""])},
			fields=["name", "start_time"],
			as_list=True,
		)
	)
	return [
		{
			"key": f"sign-up:{function.name}",
			"kind": "sign-up",
			"title": function.function_name,
			"date": str(function.start_date),
			"time": get_time(times.get(function.name)),
			"status": function.status,
			"route": f"/function-sign-up/{function.sign_up}" if function.sign_up else None,
		}
		for function in functions
	]


def get_serving_entries(person: str) -> list[dict]:
	"""An assignment the member accepted. A pending one is a request, and a declined one is gone."""
	return [
		{
			"key": f"serving:{row.name}",
			"kind": "serving",
			"title": row.function_name,
			"date": str(row.start_date),
			"time": get_time(row.start_time),
			"who": row.position,
			"status": None,
			"route": "/ministry-team",
		}
		for row in get_own_assignments(person)
		if row.status not in (PENDING, DECLINED) and str(row.start_date) >= today()
	]


def get_group_entries(person: str) -> list[dict]:
	"""The next meetings of the member's groups, by the portal's one rule for them (get_portal_groups)."""
	groups = [group.name for group in get_portal_groups(person, ["name"], limit_page_length=0)]
	if not groups:
		return []
	# church-scope: the meetings of the member's own groups
	meetings = frappe.get_all(
		"Function",
		filters={
			"group": ("in", groups),
			"auto_repeat": 0,
			"did_not_meet": 0,
			"start_date": ("between", [today(), add_days(today(), LOOK_AHEAD_DAYS)]),
		},
		fields=["name", "group", "function_name", "start_date", "start_time"],
	)
	# church-scope: the titles of the member's own groups
	titles = dict(
		frappe.get_all("Group", filters={"name": ("in", groups)}, fields=["name", "group_name"], as_list=True)
	)
	return [
		{
			"key": f"group:{meeting.name}",
			"kind": "group",
			"title": titles.get(meeting.group) or meeting.function_name,
			"date": str(meeting.start_date),
			"time": get_time(meeting.start_time),
			"status": None,
			"route": f"/groups/{meeting.group}",
		}
		for meeting in meetings
	]


def get_requests_to_answer(person: str) -> list[dict]:
	"""Serving requests the member has not answered yet, soonest first."""
	return [
		{
			"name": row.name,
			"title": row.function_name,
			"position": row.position,
			"date": str(row.start_date),
			"date_display": formatdate(row.start_date, LONG_DATE_FORMAT),
			"time": get_time(row.start_time),
		}
		for row in get_own_assignments(person)
		if row.status == PENDING and not row.has_started
	]


def get_check_in(person: str) -> dict | None:
	"""Who the member may check in now, while a Function is open for it. None when none is open."""
	try:
		require_page("household")
	except frappe.PermissionError:
		return None

	functions = get_functions()
	if not functions:
		return None

	_family, rows = get_member_rows(person)
	return {
		"functions": [
			{"name": function.name, "title": function.function_name, "time": get_time(function.start_time)}
			for function in functions
		],
		"people": [
			{"name": member.name, "display_name": member.display_name} for member in get_check_in_people(rows)
		],
	}


def get_notices() -> list[dict]:
	"""The announcements the church shares from its newest published bulletins."""
	bulletins = frappe.get_all(
		"Bulletin",
		filters=church_filters(
			selected_church_name(),
			**{"publish": 1, "share_announcements": 1, "announcements": ("is", "set")},
		),
		fields=["name", "function_name", "function_date", "announcements"],
		order_by="function_date desc",
		limit=NOTICE_BULLETINS,
	)
	return [
		{
			"name": bulletin.name,
			"title": bulletin.function_name,
			"date_display": formatdate(bulletin.function_date, LONG_DATE_FORMAT),
			"announcements": sanitize_html(bulletin.announcements, always_sanitize=True),
		}
		for bulletin in bulletins
	]


def get_newest_bulletin() -> dict | None:
	"""The newest published bulletin the member reads, to open or to download as a PDF."""
	bulletins = frappe.get_all(
		"Bulletin",
		filters={"publish": 1, **church_query_filters({})},
		fields=["name", "function_name", "function_date"],
		order_by="function_date desc",
		limit=1,
	)
	if not bulletins:
		return None
	bulletin = bulletins[0]
	return {
		"name": bulletin.name,
		"title": bulletin.function_name,
		"date_display": formatdate(bulletin.function_date, LONG_DATE_FORMAT),
	}


def get_members_pages() -> list[dict]:
	"""The members-only Web Pages this member may open."""
	if not can_open_members_only_pages():
		return []
	pages = get_members_only_pages()
	titles = dict(
		frappe.get_all(
			"Web Page",
			filters={"name": ("in", [page.name for page in pages] or [""])},
			fields=["name", "title"],
			as_list=True,
		)
	)
	return [
		{"name": page.name, "title": titles.get(page.name) or page.name, "route": "/" + page.route.strip("/")}
		for page in pages
		if page.route and not page.dynamic_route
	]


def get_prayer_requests() -> list[dict]:
	"""The newest requests the church shares for prayer, as the community page lists them."""
	open_filters, or_filters = get_open_request_filters()
	conditions = {**get_community_filters(), **open_filters}
	allowed = get_permitted_fields("Prayer Request")
	rows = frappe.get_list(
		"Prayer Request",
		fields=[field for field in ("name", "title", "request", "prayer_count") if field in allowed],
		filters=[[field, *condition] for field, condition in conditions.items()],
		or_filters=or_filters,
		order_by="urgent desc, modified desc",
		limit_page_length=PRAYER_REQUESTS,
		ignore_permissions=True,
	)
	return [
		{
			"name": row.name,
			"title": row.get("title"),
			"request": row.get("request"),
			"prayer_count": cint(row.get("prayer_count")),
		}
		for row in rows
	]


def group_by_day(entries: list[dict]) -> list[dict]:
	"""The entries in days, in order: [{date, label, is_today, entries}]."""
	days: dict[str, list[dict]] = {}
	for entry in entries:
		days.setdefault(entry["date"], []).append(format_entry(entry))
	return [
		{
			"date": date,
			"label": formatdate(date, LONG_DATE_FORMAT),
			"is_today": date == today(),
			"entries": rows,
		}
		for date, rows in days.items()
	]


def format_entry(entry: dict) -> dict:
	"""An entry with its date ready to show in a tight list."""
	return {**entry, "date_display": formatdate(getdate(entry["date"]))}


def get_time(value) -> str | None:
	"""A Time value as "HH:mm:ss", or None."""
	return format_time(value, "HH:mm:ss") if value else None
