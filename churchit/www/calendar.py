# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import date
from urllib.parse import urlencode

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import add_months, flt, get_time, get_url, getdate, sbool

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import church_filters, is_multi_church
from churchit.church_website.footer import map_url

no_cache = 1

# The Function fields an event shows.
EVENT_FIELDS = [
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
	"type",
	"church",
	"meeting_url",
]


def get_context(context):
	context.no_cache = 1
	context.title = "Calendar"
	# Public calendar shows -1 month to +6 months from today.
	today = getdate()
	context.window_start = add_months(today, -1)
	context.window_end = add_months(today, 6)

	church = selected_church_name()
	context.has_branches = bool(get_published_branches(church))
	query = f"?{urlencode({'church': church})}" if church else ""
	context.feed_url = get_url(f"/api/method/churchit.ics.get_public_calendar{query}")
	context.webcal_url = "webcal://" + context.feed_url.partition("://")[2]


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_events(start: str | date, end: str | date, include_branches: bool | str = False):
	"""Return published Functions that take place on any day in [start, end]; a blank end_date means one day.

	*include_branches* adds the Functions of the selected church's published branches.
	"""
	start_date = getdate(start)
	end_date = getdate(end)

	# Clamp the requested range to the public window to prevent scraping.
	today = getdate()
	window_start = add_months(today, -1)
	window_end = add_months(today, 6)
	if start_date < window_start:
		start_date = window_start
	if end_date > window_end:
		end_date = window_end

	church = selected_church_name()
	filters = church_filters(church, publish=1, is_link_only=0, start_date=["<=", end_date])
	branches = get_published_branches(church) if sbool(include_branches) else []
	if branches:
		# church_filters names the church and the shared records; the branches join them.
		filters["church"] = ("in", [*filters["church"][1], *branches])

	rows = frappe.get_all(
		"Function",
		filters=filters,
		or_filters=[["end_date", ">=", start_date], ["start_date", ">=", start_date]],
		fields=EVENT_FIELDS,
		order_by="start_date asc, start_time asc",
		limit_page_length=500,
	)
	return as_events(rows)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_event(name: str) -> dict | None:
	"""One published Function for a ``?event=`` link, link-only ones too, or None.

	A Function of an unpublished church is refused like an unpublished Function.
	"""
	row = frappe.db.get_value("Function", {"name": name, "publish": 1}, EVENT_FIELDS, as_dict=True)
	if not row:
		return None
	if is_multi_church() and row.church and not frappe.db.get_value("Church", row.church, "publish"):
		return None
	return as_events([row])[0]


def get_published_branches(church: str | None) -> list[str]:
	"""The published churches below *church*."""
	if not church or not is_multi_church():
		return []
	lft, rgt = frappe.db.get_value("Church", church, ["lft", "rgt"])
	return frappe.get_all(
		"Church",
		filters={"lft": [">", lft], "rgt": ["<", rgt], "publish": 1},
		pluck="name",
		order_by="lft asc",
	)


def as_events(rows: list[dict]) -> list[dict]:
	"""*rows* of Function as FullCalendar events, with their rooms, place and church."""
	rooms = get_rooms(rows)
	addresses, coordinates = {}, {}
	events = []
	for r in rows:
		address = _format_address(r.address, addresses)
		events.append(
			{
				"id": r.name,
				"title": r.function_name or r.title or r.name,
				"start": _combine(r.start_date, r.start_time, r.all_day),
				"end": _combine(r.end_date or r.start_date, r.end_time, r.all_day),
				"allDay": bool(r.all_day),
				"type": r.type,
				"address": address,
				"coordinates": get_address_coordinates(r.address, coordinates),
				"map_url": map_url(address),
				"rooms": rooms.get(r.name, []),
				"church_name": r.church and frappe.get_cached_value("Church", r.church, "church_name"),
				"meeting_url": r.meeting_url,
				"description": r.description,
			}
		)
	return events


def get_rooms(functions: list[dict]) -> dict[str, list[str]]:
	"""The room names of the Approved bookings of each of *functions*, of the Function's church or shared."""
	if not functions:
		return {}
	churches = {function.name: function.church or "" for function in functions}
	rooms = {}
	# church-scope: the bookings of Functions this page already read for its church; the loop drops a
	# booking of another church, because Room Booking does not check the church of its Function
	for booking in frappe.get_all(
		"Room Booking",
		filters={"function": ["in", list(churches)], "status": "Approved", "room": ["is", "set"]},
		fields=["function", "room", "church"],
		order_by="start_datetime asc",
	):
		if is_multi_church() and booking.church not in ("", None, churches[booking.function]):
			continue
		names = rooms.setdefault(booking.function, [])
		room_name = frappe.get_cached_value("Room", booking.room, "room_name")
		if room_name not in names:
			names.append(room_name)
	return rooms


def _format_address(address_name, cache):
	"""Render a Function's linked Address as a single readable street line."""
	if not address_name:
		return None
	if address_name in cache:
		return cache[address_name]
	parts = (
		frappe.db.get_value(
			"Address",
			address_name,
			["address_line1", "address_line2", "city", "state", "pincode", "country"],
			as_dict=True,
		)
		or {}
	)
	pieces = [
		parts.get("address_line1"),
		parts.get("address_line2"),
		", ".join(p for p in [parts.get("city"), parts.get("state"), parts.get("pincode")] if p) or None,
		parts.get("country"),
	]
	formatted = ", ".join(p for p in pieces if p) or address_name
	cache[address_name] = formatted
	return formatted


def get_address_coordinates(address_name: str | None, cache: dict) -> list[float] | None:
	"""[latitude, longitude] of a Function's linked Address, or None when it has not been placed."""
	if not address_name:
		return None
	if address_name not in cache:
		place = frappe.db.get_value("Address", address_name, ["latitude", "longitude"], as_dict=True)
		placed = place and (flt(place.latitude) or flt(place.longitude))
		cache[address_name] = [flt(place.latitude), flt(place.longitude)] if placed else None
	return cache[address_name]


def _combine(date_value, time_value, all_day):
	"""Build an ISO string FullCalendar v3 accepts."""
	if not date_value:
		return None
	if all_day or not time_value:
		return str(date_value)
	# Time columns come back as timedelta, whose str() drops the leading zero.
	return f"{date_value}T{get_time(time_value)}"
