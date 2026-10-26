# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""iCalendar feeds: the building blocks every feed shares, and the public church calendar."""

import hashlib
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_months, get_host_name, get_system_timezone, getdate
from werkzeug.wrappers import Response

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_scope import church_filters
from churchit.www.calendar import _format_address

# RFC 5545 3.1: a content line holds at most 75 octets, not counting the line break.
LINE_OCTETS = 75


def fold(line: str) -> str:
	"""*line* split into lines of 75 octets or less, each continuation led by a space.

	It splits between characters, never inside a UTF-8 character.
	"""
	lines, current, size = [], "", 0
	for character in line:
		octets = len(character.encode())
		# A continuation line spends one octet on its leading space.
		limit = LINE_OCTETS - 1 if lines else LINE_OCTETS
		if size + octets > limit:
			lines.append(current)
			current, size = "", 0
		current += character
		size += octets
	return "\r\n ".join([*lines, current])


def make_event(
	uid: str,
	function,
	summary: str,
	stamp: datetime,
	description: str | None = None,
	location: str | None = None,
	url: str | None = None,
) -> list[str]:
	"""One VEVENT at the times of *function*, stamped with *stamp*, when its content last changed.

	*uid* names the record on this site; the event keeps it for as long as the record lives.
	"""
	lines = [
		"BEGIN:VEVENT",
		f"UID:{uid}@{get_host_name()}",
		f"DTSTAMP:{as_calendar_time(stamp)}",
		*calendar_times(function),
		f"SUMMARY:{calendar_text(summary)}",
	]
	if description:
		lines.append(f"DESCRIPTION:{calendar_text(description)}")
	if location:
		lines.append(f"LOCATION:{calendar_text(location)}")
	# A URI value, not text, so it is not escaped: a line break in it would start a new property.
	if url and "\r" not in url and "\n" not in url:
		lines.append(f"URL:{url}")
	return [*lines, "END:VEVENT"]


def make_calendar(name: str, events: list[list[str]]) -> str:
	"""A calendar called *name* that holds *events*, from ``make_event``, with every line folded."""
	lines = [
		"BEGIN:VCALENDAR",
		"VERSION:2.0",
		"PRODID:-//Churchit//Calendar//EN",
		"METHOD:PUBLISH",
		f"X-WR-CALNAME:{calendar_text(name)}",
		*(line for event in events for line in event),
		"END:VCALENDAR",
	]
	return "\r\n".join(fold(line) for line in lines) + "\r\n"


def calendar_response(body: str, filename: str) -> Response:
	"""*body* as a calendar file, or an empty 304 when the calendar app already holds this version."""
	etag = hashlib.sha256(body.encode()).hexdigest()
	if frappe.request.if_none_match.contains_weak(etag):
		response = Response(status=304)
	else:
		response = Response(body, content_type="text/calendar; charset=utf-8")
		response.headers["Content-Disposition"] = f'inline; filename="{filename}"'
	# Frappe's default no-store would forbid keeping the copy that the ETag revalidates.
	response.headers["Cache-Control"] = "private, no-cache"
	response.set_etag(etag)
	return response


def calendar_times(function) -> list[str]:
	"""DTSTART and DTEND of *function*: whole days when it has no start time, else UTC times."""
	start, end = get_time_window(function)
	if function.all_day or not function.start_time:
		# The end of an all-day event is the day after its last day.
		return [f"DTSTART;VALUE=DATE:{start:%Y%m%d}", f"DTEND;VALUE=DATE:{end + timedelta(days=1):%Y%m%d}"]
	return [f"DTSTART:{as_calendar_time(start)}", f"DTEND:{as_calendar_time(end)}"]


def as_calendar_time(value: datetime) -> str:
	"""*value*, a time in the site's time zone, as an iCalendar UTC time."""
	local = value.replace(tzinfo=ZoneInfo(get_system_timezone()))
	return local.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def calendar_text(value: str) -> str:
	"""*value* escaped for an iCalendar text property."""
	value = value.replace("\r\n", "\n").replace("\r", "\n")
	return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_public_calendar(ministry: str | None = None):
	"""The selected church's published Functions over the /calendar window, as a calendar feed.

	The church comes from ``?church=``. A ``?ministry=`` that is not published gives an empty calendar.
	"""
	church = selected_church_name()
	today = getdate()
	window_start = add_months(today, -1)
	filters = church_filters(church, publish=1, is_link_only=0, start_date=["<=", add_months(today, 6)])
	if ministry:
		filters["associated_ministry"] = ministry

	rows = []
	if not ministry or frappe.db.exists("Ministry", {"name": ministry, "publish": 1}):
		rows = frappe.get_all(
			"Function",
			filters=filters,
			or_filters=[["end_date", ">=", window_start], ["start_date", ">=", window_start]],
			fields=[
				"name",
				"function_name",
				"title",
				"start_date",
				"start_time",
				"end_date",
				"end_time",
				"all_day",
				"address",
				"description",
				"meeting_url",
				"modified",
			],
			order_by="start_date asc, start_time asc",
		)

	addresses = {}
	events = [
		make_event(
			row.name,
			row,
			row.function_name or row.title or row.name,
			row.modified,
			description=row.description,
			location=_format_address(row.address, addresses),
			url=row.meeting_url,
		)
		for row in rows
	]
	name = church and frappe.db.get_value("Church", church, "church_name")
	return calendar_response(make_calendar(name or _("Calendar"), events), "calendar.ics")
