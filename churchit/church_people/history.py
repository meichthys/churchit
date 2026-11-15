# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The records about a person that show in the Person timeline: visits, care requests, dated life events,
member transfers and connection cards.

Each is read with `frappe.get_list`, so the reader's roles, church and User Permissions decide which records
show, and Frappe leaves out every field above the reader's permission level. `get_list` runs no
`has_permission` hook on each record, so a doctype read here must have none (`test_history`). Counseling cases
and background checks never show.
"""

from datetime import date, datetime

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import formatdate, get_url_to_form, getdate

from churchit.utils import link_title

# The newest records of each kind. Older ones stay in their lists and on the Person form.
LIMIT = 20
CARD_TEMPLATE = "churchit/church_people/history_card.html"


def get_timeline_content(doctype: str, docname: str) -> list[dict]:
	"""additional_timeline_content hook for Person: the records about the person the reader may read, as cards."""
	return [
		*get_visit_cards(docname),
		*get_care_request_cards(docname),
		*get_life_event_cards(docname),
		*get_transfer_cards(docname),
		*get_connection_cards(docname),
	]


def get_visit_cards(person: str) -> list[dict]:
	visits = get_readable_rows(
		"Visitation Log", {"person": person}, "visit_date", ["visit_type", "status", "visited_by"]
	)
	return [
		make_card(
			"house",
			visit,
			visit.visit_date,
			heading=(_("Visit"), visit.visit_type),
			details=(_(visit.status), name_in(_("By {0}"), visit.visited_by)),
			url=get_url_to_form("Visitation Log", visit.name),
		)
		for visit in visits
	]


def get_care_request_cards(person: str) -> list[dict]:
	requests = get_readable_rows(
		"Care Request", {"person": person}, "submitted_on", ["category", "status", "caregiver"]
	)
	return [
		make_card(
			"hand-heart",
			request,
			request.submitted_on,
			heading=(_("Care Request"), request.category),
			details=(_(request.status), name_in(_("Caregiver: {0}"), request.caregiver)),
			url=get_url_to_form("Care Request", request.name),
		)
		for request in requests
	]


def get_life_event_cards(person: str) -> list[dict]:
	"""The person's life events with a full date. One whose year is unknown has no place on the timeline.

	`get_list` does not check the permission level of the Person table, so it is checked here as the form does.
	"""
	permlevel = frappe.get_meta("Person").get_field("life_events").permlevel
	if permlevel and permlevel not in frappe.get_lazy_doc("Person", person).get_permlevel_access("read"):
		return []

	filters = {"parent": person, "parenttype": "Person", "date": ("is", "set"), "year_unknown": 0}
	events = get_readable_rows(
		"Life Event", filters, "date", ["event_type", "location", "officiant"], parent_doctype="Person"
	)
	return [
		make_card(
			"calendar-heart",
			event,
			event.date,
			heading=(event.event_type,),
			details=(event.location, name_in(_("Officiant: {0}"), event.officiant)),
		)
		for event in events
	]


def get_transfer_cards(person: str) -> list[dict]:
	transfers = get_readable_rows(
		"Member Transfer",
		{"person": person},
		"letter_date",
		["direction", "status", "other_church", "to_church"],
	)
	return [
		make_card(
			"arrow-right-left",
			transfer,
			transfer.letter_date,
			heading=(_("Transfer In") if transfer.direction == "In" else _("Transfer Out"),),
			details=(
				link_title("Church", transfer.to_church) if transfer.to_church else transfer.other_church,
				_(transfer.status),
			),
			url=get_url_to_form("Member Transfer", transfer.name),
		)
		for transfer in transfers
	]


def get_connection_cards(person: str) -> list[dict]:
	cards = get_readable_rows(
		"Connection Card", {"person": person, "status": ("!=", "Spam")}, "creation", ["visit", "status"]
	)
	return [
		make_card(
			"contact",
			card,
			card.creation,
			heading=(_("Connection Card"), _(card.visit)),
			details=(_(card.status),),
			url=get_url_to_form("Connection Card", card.name),
		)
		for card in cards
	]


def get_readable_rows(
	doctype: str, filters: dict, date_field: str, fields: list[str], parent_doctype: str | None = None
) -> list[frappe._dict]:
	"""The newest *doctype* rows the reader may read, without the *fields* above their permission level.

	Frappe refuses a filter or sort on such a field, so a reader who may not read the *filters* fields or
	*date_field* gets no rows rather than an error that stops the Person form from opening.
	"""
	if not frappe.has_permission(doctype, parent_doctype=parent_doctype):
		return []

	if not {*filters, date_field} <= set(get_permitted_fields(doctype, parenttype=parent_doctype)):
		return []

	return frappe.get_list(
		doctype,
		filters=filters,
		fields=["name", *{"creation", date_field}, *fields],
		order_by=f"{date_field} desc, creation desc",
		limit=LIMIT,
		parent_doctype=parent_doctype,
	)


def name_in(text: str, person: str | None) -> str | None:
	"""*text* with the person's name in it, or nothing when no person is set."""
	return text.format(link_title("Person", person)) if person else None


def make_card(
	icon: str,
	row: frappe._dict,
	recorded_on: date | None,
	heading: tuple,
	details: tuple,
	url: str | None = None,
) -> dict:
	"""One record as a timeline card, placed on the day it records at the time it was added."""
	day = getdate(recorded_on or row.creation)
	context = {
		"heading": " · ".join(filter(None, heading)),
		"date": formatdate(day),
		"details": " · ".join(filter(None, details)),
		"url": url,
	}
	return {
		"icon": icon,
		"is_card": True,
		"creation": datetime.combine(day, row.creation.time()),
		"content": frappe.render_template(  # nosemgrep: frappe-ssti
			CARD_TEMPLATE, context
		),
		"url": url,
	}
