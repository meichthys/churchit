# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

from churchit.church_operations.doctype.room_booking.room_booking import get_bookable_rooms
from churchit.church_scope import session_person


def get_context(context):
	"""Offer only the rooms the member may ask for, in place of the options Frappe found."""
	rooms = get_bookable_rooms()
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "room":
			field.options = json.dumps([{"value": name, "label": title} for name, title in rooms.items()])


def get_list_context(context):
	"""List only the login's own requests, not every booking that staff may read.

	A blocked time has no requester, so a login with no Person would otherwise list them.
	"""
	context.filters = {"requester": session_person(), "status": ("!=", "Blocked")}
	return context
