# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Prayer, care and benevolence requests in the member app.

A member changes these through Frappe's web form accept and delete, which keep each form's field list,
the page switches and the controllers' rules. The reads here send explicit fields only.
"""

import html

import frappe
from frappe import _
from frappe.templates.includes.comments.comments import add_comment
from frappe.utils import formatdate, getdate, now_datetime, strip_html

from churchit.church_finances.doctype.alms_request.alms_request import is_reviewed
from churchit.church_people.member_access import RECIPIENT_DOCTYPES
from churchit.church_prayers.prayer_access import (
	PRAYER_TEAM,
	PRAYER_TEAM_ROLE,
	get_community_filters,
	get_open_request_filters,
)
from churchit.church_scope import session_person
from churchit.church_website.api import search_church_recipient
from churchit.portal.access import require_page, require_person
from churchit.portal.realtime import notify

COMMUNITY_FORM = "community-prayer-requests"
COMMENT_FORMS = {"prayer-request": ("Prayer Request", "prayer"), "alms-request": ("Alms Request", "alms")}
COMMUNITY_FIELDS = [
	"name",
	"title",
	"type",
	"status",
	"urgent",
	"visibility",
	"recipient_name",
	"request",
	"prayer_count",
	"modified",
]


def get_options(doctype: str) -> list[dict]:
	"""The names and descriptions of a request type. Members cannot read these doctypes, so this reads past permissions."""
	return frappe.get_all(doctype, fields=["name", "description"], order_by="name asc")


def get_select_options(doctype: str, fieldname: str) -> list[str]:
	return [option for option in frappe.get_meta(doctype).get_field(fieldname).options.split("\n") if option]


def get_prayer_row(row: dict) -> dict:
	return {**row, "date": str(getdate(row["modified"])), "date_display": formatdate(row["modified"])}


@frappe.whitelist(methods=["GET"])
def get_my_prayer_requests() -> dict:
	"""The prayer requests the member made, newest change first. Reads only."""
	require_person()
	require_page("prayer-request")
	rows = frappe.get_list(
		"Prayer Request",
		filters={"owner": frappe.session.user},
		fields=[*COMMUNITY_FIELDS, "recipient_type", "recipient", "approved_for_list"],
		order_by="modified desc",
		limit=0,
	)
	return {"items": [get_prayer_row(row) for row in rows], "can_add": True}


@frappe.whitelist(methods=["GET"])
def get_prayer_form() -> dict:
	"""What the prayer request form offers: types, who can see it and the member's own Person. Reads only."""
	person = require_person()
	require_page("prayer-request")
	return {
		"types": get_options("Prayer Request Type"),
		"visibilities": [
			{"name": "Private", "description": _("Only you and the pastoral care team.")},
			{"name": "Prayer Team", "description": _("Also the prayer team.")},
			{"name": "Whole Church", "description": _("Every member, on the prayer list.")},
		],
		"recipient_doctypes": list(RECIPIENT_DOCTYPES),
		"me": {"name": person, "full_name": frappe.db.get_value("Person", person, "full_name")},
	}


@frappe.whitelist(methods=["GET"])
def search_recipients(doctype: str, txt: str | None = None) -> dict:
	"""Names a request may be for, from the member's church. Reads only."""
	require_person()
	return {"items": search_church_recipient(doctype, txt)}


def get_prayed_today(person: str, names: list[str]) -> set[str]:
	"""The requests among *names* that *person* recorded a prayer for today."""
	# church-scope: the member's own prayers, by person
	prayers = frappe.get_all(
		"Prayer", filters={"person": person, "date": (">=", getdate(now_datetime()))}, pluck="name"
	)
	if not prayers or not names:
		return set()
	return set(
		frappe.get_all(
			"Prayer Topic",
			filters={"parenttype": "Prayer", "parent": ("in", prayers), "topic": ("in", names)},
			pluck="topic",
		)
	)


@frappe.whitelist(methods=["GET"])
def get_community_requests() -> dict:
	"""The church's open, approved prayer requests the member may read, urgent first. Reads only.

	It sends no requester, owner, church or end date.
	"""
	person = require_person()
	require_page("community-prayer-requests")
	filters, or_filters = get_open_request_filters()
	rows = frappe.get_list(
		"Prayer Request",
		filters={**get_community_filters(), **filters},
		or_filters=or_filters,
		fields=COMMUNITY_FIELDS,
		order_by="urgent desc, modified desc",
		limit=0,
		ignore_permissions=True,
	)
	prayed = get_prayed_today(person, [row.name for row in rows])
	return {"items": [{**get_prayer_row(row), "prayed_today": row.name in prayed} for row in rows]}


@frappe.whitelist(methods=["GET"])
def get_community_request(name: str) -> dict:
	"""One prayer request from the prayer list, with its comments. Reads only."""
	person = require_person()
	require_page("community-prayer-requests")
	request = frappe.get_doc("Prayer Request", name)
	if not (request.has_webform_permission() or frappe.has_permission("Prayer Request", "read", doc=request)):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	row = get_prayer_row({field: request.get(field) for field in COMMUNITY_FIELDS})
	return {
		**row,
		"prayed_today": name in get_prayed_today(person, [name]),
		"is_team_only": request.visibility == PRAYER_TEAM and PRAYER_TEAM_ROLE in frappe.get_roles(),
		"comments": get_comments(name),
	}


def get_comments(name: str, doctype: str = "Prayer Request") -> list[dict]:
	"""Comments on a request that are published or the member's own, by name and time only."""
	rows = frappe.get_all(
		"Comment",
		filters={"reference_doctype": doctype, "reference_name": name, "comment_type": "Comment"},
		or_filters=[["owner", "=", frappe.session.user], ["published", "=", 1]],
		fields=["name", "comment_by", "content", "creation"],
		order_by="creation asc",
	)
	return [
		{
			"name": row.name,
			"comment_by": row.comment_by,
			"content": html.unescape(strip_html(row.content or "")),
			"date_display": formatdate(row.creation),
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def add_prayer_comment(prayer_request: str, comment: str) -> dict:
	"""Comment on a prayer request the member may read. Changes data.

	Frappe's comment rules apply: no links and no email addresses.
	"""
	require_person()
	require_page("community-prayer-requests")
	request = frappe.get_doc("Prayer Request", prayer_request)
	if not (request.has_webform_permission() or frappe.has_permission("Prayer Request", "read", doc=request)):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	if add_comment(comment, "", "", "Prayer Request", prayer_request, "", COMMUNITY_FORM) is False:
		frappe.clear_messages()
		frappe.throw(_("Write a comment without links or email addresses."))

	notify(request.owner, "prayer", prayer_request)
	return {"comments": get_comments(prayer_request)}


def get_own_request(form: str, name: str):
	"""The member's own request on a form that allows comments. Refuses a switched-off page."""
	if form not in COMMENT_FORMS:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	require_person()
	require_page(form)
	doctype, _topic = COMMENT_FORMS[form]
	frappe.has_permission(doctype, "read", doc=name, throw=True)
	request = frappe.get_doc(doctype, name)
	if request.owner != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return request


@frappe.whitelist(methods=["GET"])
def get_request_comments(form: str, name: str) -> dict:
	"""The comments on one of the member's own prayer or benevolence requests. Reads only."""
	request = get_own_request(form, name)
	return {"comments": get_comments(name, request.doctype)}


@frappe.whitelist(methods=["POST"])
def add_request_comment(form: str, name: str, comment: str) -> dict:
	"""Comment on one of the member's own prayer or benevolence requests. Changes data.

	Frappe's comment rules apply: no links and no email addresses.
	"""
	request = get_own_request(form, name)
	if add_comment(comment, "", "", request.doctype, name, "", form) is False:
		frappe.clear_messages()
		frappe.throw(_("Write a comment without links or email addresses."))

	notify(request.owner, COMMENT_FORMS[form][1], name)
	return {"comments": get_comments(name, request.doctype)}


@frappe.whitelist(methods=["GET"])
def get_my_care_requests() -> dict:
	"""The care requests the member made, newest change first. Reads only."""
	require_person()
	require_page("care-request")
	rows = frappe.get_list(
		"Care Request",
		filters={"owner": frappe.session.user},
		fields=["name", "category", "urgency", "status", "submitted_on", "description", "preferred_contact"],
		order_by="modified desc",
		limit=0,
	)
	items = [{**row, "date_display": formatdate(row.submitted_on)} for row in rows]
	return {"items": items, "can_add": True}


@frappe.whitelist(methods=["GET"])
def get_care_form() -> dict:
	"""What the care request form offers: categories, urgencies and ways to be reached. Reads only."""
	require_person()
	require_page("care-request")
	return {
		"categories": get_options("Care Request Type"),
		"urgencies": get_select_options("Care Request", "urgency"),
		"preferred_contacts": get_select_options("Care Request", "preferred_contact"),
		"default_urgency": "Medium",
	}


@frappe.whitelist(methods=["GET"])
def get_my_alms_requests() -> dict:
	"""The benevolence requests the member made. A request can change only until the church reviews it. Reads only."""
	require_person()
	require_page("alms-request")
	rows = frappe.get_list(
		"Alms Request",
		filters={"owner": frappe.session.user},
		fields=[
			"name",
			"title",
			"recipient_type",
			"recipient",
			"amount",
			"description",
			"status",
			"associated_expense",
			"modified",
		],
		order_by="modified desc",
		limit=0,
	)
	items = [
		{
			"name": row.name,
			# .get(): the published-field scan reads any `.title` as a read of every doctype's title here.
			"recipient_name": row.get("title"),
			"recipient_type": row.recipient_type,
			"recipient": row.recipient,
			"amount": row.amount,
			"description": row.description,
			"status": row.status,
			"date_display": formatdate(row.modified),
			"can_change": not is_reviewed(row),
		}
		for row in rows
	]
	person = session_person()
	return {
		"items": items,
		"can_add": bool(person),
		"me": {"name": person, "full_name": frappe.db.get_value("Person", person, "full_name")},
	}
