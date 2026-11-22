# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Serving and room requests for the member app: the team schedule, blocks, and room bookings."""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import format_date, format_datetime, get_datetime, now_datetime

from churchit.church_ministries.doctype.function.function import get_team_schedule
from churchit.church_ministries.member_ministry_team import (
	get_calendar_links,
	get_own_assignments,
	get_own_blocks,
	get_own_positions,
)
from churchit.church_operations.doctype.room_booking.room_booking import get_bookable_rooms
from churchit.portal.access import require_page, require_person
from churchit.utils import LONG_DATE_FORMAT

PENDING = "Pending"
ACCEPTED = "Accepted"
DECLINED = "Declined"
READ_ONLY_BOOKING_STATUSES = ("Cancelled", "Completed", "Blocked")
LOCKED_BOOKING_STATUSES = (*READ_ONLY_BOOKING_STATUSES, "Denied")
REQUEST_LIMIT = 30
BOOKING_FIELDS = ["name", "room", "purpose", "notes", "start_datetime", "end_datetime", "status"]


@frappe.whitelist(methods=["GET"])
def get_serving() -> dict:
	"""The signed-in member's serving requests, blocks, positions and calendar link. Reads only."""
	person = require_person()
	require_page("ministry-team")

	schedules: dict[str, frappe._dict] = {}
	return {
		"assignments": [get_assignment_row(row, person, schedules) for row in get_own_assignments(person)],
		"blocks": [get_block_row(block) for block in get_own_blocks(person)],
		"positions": [
			{
				"position": row.position,
				"title": row.title,
				"max_times_per_month": row.max_times_per_month or 0,
			}
			for row in get_own_positions(person)
		],
		"calendar": get_calendar_links(person),
	}


def get_assignment_row(row: frappe._dict, person: str, schedules: dict[str, frappe._dict]) -> dict:
	"""One assignment with the answers the member may still give and the team's schedule for it.

	*schedules* holds the schedule of each function already read, so a function is read once.
	"""
	is_open = not row.has_started and not row.replaced_by
	if row.function not in schedules:
		# church-scope: the schedule of a function the member's own assignment names
		function = frappe.get_doc("Function", row.function)
		schedules[row.function] = get_team_schedule(function, person)
	schedule = schedules[row.function]

	return {
		"name": row.name,
		"status": row.status,
		"decline_reason": row.decline_reason,
		"function": row.function,
		"function_name": row.function_name,
		"position": row.position,
		"start_date": str(row.start_date),
		"end_date": str(row.end_date) if row.end_date else None,
		"date_label": format_date(row.start_date, LONG_DATE_FORMAT),
		"start_time": str(row.start_time) if row.start_time and not row.all_day else None,
		"meeting_url": row.meeting_url if (row.meeting_url or "").startswith("https://") else None,
		"replaced_by": row.replaced_by,
		"pending_replacement": row.pending_replacement,
		"needs_answer": is_open and row.status == PENDING,
		"can_accept": is_open and row.status != ACCEPTED,
		"can_decline": not row.has_started and row.status != DECLINED,
		"can_pass_on": not row.has_started and row.can_pass_on and not row.pending_replacement,
		"schedule": [get_schedule_row(item) for item in schedule.rows],
		"need_notes": [{"position": note.position, "notes": note.notes} for note in schedule.need_notes],
	}


def get_schedule_row(item: frappe._dict) -> dict:
	"""One row of a service schedule, as the app shows it."""
	return {
		"time": item.time,
		"title": item.title,
		"detail": item.detail,
		"is_header": bool(item.is_header),
		"key": item.get("key"),
		"arrangement": item.get("arrangement"),
		"notes": item.get("notes"),
		"media": [{"label": media.label, "url": media.url} for media in item.get("media") or []],
	}


def get_block_row(block: frappe._dict) -> dict:
	"""One block-out date range, as the app shows it."""
	return {
		"name": block.name,
		"from_date": str(block.from_date),
		"to_date": str(block.to_date),
		"reason": block.reason,
		"whole_household": bool(block.whole_household),
		"repeat_frequency": block.repeat_frequency,
		"repeat_until": format_date(block.repeat_until) if block.repeat_until else None,
	}


@frappe.whitelist(methods=["GET"])
def get_rooms() -> dict:
	"""The rooms the signed-in member may ask for: their church's bookable rooms and shared ones. Reads only."""
	require_person()
	require_page("room-request")

	return {"rooms": [{"name": name, "room_name": title} for name, title in get_bookable_rooms().items()]}


@frappe.whitelist(methods=["GET"])
def get_room_requests() -> dict:
	"""The signed-in member's own room requests, the coming ones soonest first, then past ones. Reads only.

	A booking that staff made for the member is not listed: members read only the bookings they made.
	"""
	person = require_person()
	require_page("room-request")

	bookings = frappe.get_list(
		"Room Booking",
		filters={"requester": person, "status": ("!=", "Blocked")},
		fields=BOOKING_FIELDS,
		order_by="start_datetime asc",
		limit_page_length=200,
	)
	now = now_datetime()
	coming = [booking for booking in bookings if get_datetime(booking.end_datetime) >= now]
	past = [booking for booking in bookings if get_datetime(booking.end_datetime) < now]
	return {"items": [get_booking_row(booking) for booking in (*coming, *reversed(past))]}


@frappe.whitelist(methods=["GET"])
def get_room_request(name: str) -> dict:
	"""One of the signed-in member's own room requests. Reads only."""
	person = require_person()
	require_page("room-request")

	booking = frappe.get_doc("Room Booking", name)
	booking.check_permission("read")
	if booking.requester != person or booking.status == "Blocked":
		frappe.throw(_("This request is not yours."), frappe.PermissionError)

	return get_booking_row(booking)


def is_editable(booking, end) -> bool:
	"""A member changes a booking that is still to come and not Denied: only an approver reopens a denied one."""
	return (
		booking.status not in LOCKED_BOOKING_STATUSES
		and end >= now_datetime()
		and frappe.has_permission("Room Booking", "write", doc=booking.name)
	)


def get_booking_row(booking) -> dict:
	"""A booking as the app shows it, with the day and times in the house style."""
	start, end = get_datetime(booking.start_datetime), get_datetime(booking.end_datetime)
	return {
		"name": booking.name,
		"room": booking.room,
		"room_name": frappe.db.get_value("Room", booking.room, "room_name") if booking.room else None,
		"purpose": booking.purpose,
		"notes": booking.notes,
		"status": booking.status,
		"start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
		"end_datetime": end.strftime("%Y-%m-%d %H:%M:%S"),
		"date_label": format_date(start, LONG_DATE_FORMAT),
		"start_time": start.strftime("%H:%M:%S"),
		"end_time": end.strftime("%H:%M:%S"),
		"ends_same_day": end.date() == start.date(),
		"end_day_label": None if end.date() == start.date() else format_datetime(end, "EEE MMM d"),
		"can_edit": is_editable(booking, end),
	}


@contextmanager
def member_rules():
	"""Apply the member rules of Room Booking, which key on the web form flag, for one save only."""
	was_set = frappe.flags.in_web_form
	frappe.flags.in_web_form = True
	try:
		yield
	finally:
		frappe.flags.in_web_form = was_set


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REQUEST_LIMIT, seconds=60 * 60, user_based=True)
def request_room(
	room: str, start_datetime: str, end_datetime: str, purpose: str, notes: str | None = None
) -> dict:
	"""Ask for a room for the signed-in member. Changes data.

	The Room Booking rules for members apply: the room must be bookable by the member, and the
	time must be still to come and last a day at most.
	"""
	person = require_person()
	require_page("room-request")

	booking = frappe.get_doc(
		{
			"doctype": "Room Booking",
			"requester": person,
			"room": room,
			"start_datetime": start_datetime,
			"end_datetime": end_datetime,
			"purpose": purpose,
			"notes": notes,
		}
	)
	with member_rules():
		booking.insert()
	return {"name": booking.name, "status": booking.status}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=REQUEST_LIMIT, seconds=60 * 60, user_based=True)
def update_room_request(
	name: str, room: str, start_datetime: str, end_datetime: str, purpose: str, notes: str | None = None
) -> dict:
	"""Change one of the signed-in member's own room requests. Changes data.

	On a room that needs approval, an approved request goes back to Requested when its room or time moves.
	A Denied request, or one that has ended, cannot be changed.
	"""
	person = require_person()
	require_page("room-request")

	booking = frappe.get_doc("Room Booking", name)
	booking.check_permission("write")
	if (
		booking.requester != person
		or booking.status in LOCKED_BOOKING_STATUSES
		or get_datetime(booking.end_datetime) < now_datetime()
	):
		frappe.throw(_("You can change only your own open requests here."), frappe.PermissionError)

	booking.update(
		{
			"room": room,
			"start_datetime": start_datetime,
			"end_datetime": end_datetime,
			"purpose": purpose,
			"notes": notes,
		}
	)
	with member_rules():
		booking.save()
	return {"name": booking.name, "status": booking.status}
