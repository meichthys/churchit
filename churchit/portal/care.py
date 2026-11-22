# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Prayer, care and benevolence requests in the member app.

A save takes only the fields its request form shows, and the request's controller applies its member
rules. The reads here send explicit fields only.
"""

import html

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.templates.includes.comments.comments import EMAIL_PATTERN, URLS_COMMENT_PATTERN, get_limit
from frappe.utils import cint, formatdate, getdate, now_datetime, strip_html
from frappe.utils.html_utils import clean_html

from churchit.church_finances.doctype.alms_request.alms_request import is_reviewed
from churchit.church_people.member_access import RECIPIENT_DOCTYPES, get_recipient_filters
from churchit.church_prayers.prayer_access import (
	COMMUNITY_FIELDS,
	PRAYER_TEAM,
	PRAYER_TEAM_ROLE,
	get_community_filters,
	get_open_request_filters,
)
from churchit.church_scope import session_person
from churchit.portal.access import require_page, require_person
from churchit.portal.realtime import notify, notify_person

COMMENT_PAGES = {"prayer-request": ("Prayer Request", "prayer"), "alms-request": ("Alms Request", "alms")}
# How many saves and deletes a member may make a minute: the limits Frappe sets on its web forms.
SAVES_A_MINUTE = 10
DELETES_A_MINUTE = 999


def get_options(doctype: str) -> list[dict]:
	"""The names and descriptions of a request type. Members cannot read these doctypes, so this reads past permissions."""
	return frappe.get_all(doctype, fields=["name", "description"], order_by="name asc")


def get_select_options(doctype: str, fieldname: str) -> list[str]:
	return [option for option in frappe.get_meta(doctype).get_field(fieldname).options.split("\n") if option]


def get_prayer_row(row: dict) -> dict:
	return {**row, "date": str(getdate(row["modified"])), "date_display": formatdate(row["modified"])}


def get_own(doctype: str, name: str, ptype: str):
	"""The session user's own *doctype* record *name*, once they may *ptype* it. Another person's is refused."""
	frappe.has_permission(doctype, ptype, doc=name, throw=True)
	doc = frappe.get_doc(doctype, name)
	if doc.owner != frappe.session.user:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


def save_request(doc, values: dict) -> dict:
	"""Save the member's new or changed request *doc* with *values*, the fields its form shows."""
	doc.update(values)
	# Staff with a Person use the app too, so the member rules cannot key on a Website User alone.
	doc.flags.from_member_app = True
	if doc.is_new():
		# Staff who ask for themselves may hold no create right on the request in the desk.
		doc.insert(ignore_permissions=True)
	else:
		doc.save()
	return {"name": doc.name}


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


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=SAVES_A_MINUTE, seconds=60, user_based=True)
def save_prayer_request(
	title: str,
	type: str,
	visibility: str,
	urgent: int = 0,
	recipient_type: str | None = None,
	recipient: str | None = None,
	request: str | None = None,
	name: str | None = None,
) -> dict:
	"""Share a prayer request, or change one of the member's own. Changes data.

	Prayer Request names a member as its requester and refuses a recipient from outside their church.
	The status and the place on the prayer list stay with the care team.
	"""
	require_person()
	require_page("prayer-request")
	doc = get_own("Prayer Request", name, "write") if name else frappe.new_doc("Prayer Request")
	values = {
		"title": title,
		"type": type,
		"visibility": visibility,
		"urgent": cint(urgent),
		"recipient_type": recipient_type,
		"recipient": recipient,
		"request": request,
	}
	return save_request(doc, values)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=DELETES_A_MINUTE, seconds=60, user_based=True)
def delete_prayer_request(name: str) -> None:
	"""Delete one of the member's own prayer requests. Changes data.

	A request that someone prayed for cannot go: its prayers link to it.
	"""
	require_person()
	require_page("prayer-request")
	get_own("Prayer Request", name, "delete")
	frappe.delete_doc("Prayer Request", name)


@frappe.whitelist(methods=["GET"])
def search_recipients(doctype: str, txt: str | None = None) -> dict:
	"""Names a request may be for, from the member's church. Reads only.

	It reads past DocPerms on purpose: a member reads only their own Person, and it sends a name and a
	title only.
	"""
	require_person()
	filters = get_recipient_filters(doctype)
	title_field = frappe.get_meta(doctype).title_field or "name"
	or_filters = [["name", "like", f"%{txt}%"], [title_field, "like", f"%{txt}%"]] if txt else None
	rows = frappe.get_all(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=["name", f"{title_field} as label"],
		order_by=f"{title_field} asc",
		limit=20,
	)
	return {"items": rows}


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


@rate_limit(limit=get_limit, seconds=60 * 60)
def add_member_comment(doc, comment: str) -> None:
	"""Publish the member's comment on *doc* under Frappe's website comment rules: no links, no email
	address and its hourly limit."""
	if not comment.strip():
		frappe.throw(_("Write a comment."))
	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		frappe.throw(_("Write a comment without links or email addresses."))

	user = frappe.session.user
	added = doc.add_comment(
		text=clean_html(comment),
		comment_email=user,
		comment_by=frappe.db.get_value("User", user, "full_name"),
	)
	added.db_set("published", 1)


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

	add_member_comment(request, comment)
	notify_person(request.requestor, "prayer", prayer_request)
	return {"comments": get_comments(prayer_request)}


def get_own_request(page: str, name: str):
	"""The member's own request on a page that takes comments. Refuses a switched-off page."""
	if page not in COMMENT_PAGES:
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	require_person()
	require_page(page)
	return get_own(COMMENT_PAGES[page][0], name, "read")


@frappe.whitelist(methods=["GET"])
def get_request_comments(page: str, name: str) -> dict:
	"""The comments on one of the member's own prayer or benevolence requests. Reads only."""
	request = get_own_request(page, name)
	return {"comments": get_comments(name, request.doctype)}


@frappe.whitelist(methods=["POST"])
def add_request_comment(page: str, name: str, comment: str) -> dict:
	"""Comment on one of the member's own prayer or benevolence requests. Changes data.

	Frappe's comment rules apply: no links and no email addresses.
	"""
	request = get_own_request(page, name)
	add_member_comment(request, comment)
	notify(request.owner, COMMENT_PAGES[page][1], name)
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


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=SAVES_A_MINUTE, seconds=60, user_based=True)
def save_care_request(
	category: str,
	description: str,
	urgency: str | None = None,
	preferred_contact: str | None = None,
	name: str | None = None,
) -> dict:
	"""Ask for care, or change one of the member's own care requests. Changes data.

	Care Request is for the member's own Person, and only the care team changes its status.
	"""
	require_person()
	require_page("care-request")
	doc = get_own("Care Request", name, "write") if name else frappe.new_doc("Care Request")
	values = {
		"category": category,
		"urgency": urgency,
		"description": description,
		"preferred_contact": preferred_contact,
	}
	return save_request(doc, values)


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


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=SAVES_A_MINUTE, seconds=60, user_based=True)
def save_alms_request(
	recipient_type: str,
	recipient: str,
	description: str,
	amount: float | None = None,
	name: str | None = None,
) -> dict:
	"""Ask the church for help, or change one of the member's own requests until it is reviewed. Changes data.

	Alms Request names the member as the requester, refuses a member's recipient from outside their church,
	and leaves the status to the care team.
	"""
	require_person()
	require_page("alms-request")
	doc = get_own("Alms Request", name, "write") if name else frappe.new_doc("Alms Request")
	values = {
		"recipient_type": recipient_type,
		"recipient": recipient,
		"description": description,
		"amount": amount,
	}
	return save_request(doc, values)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=DELETES_A_MINUTE, seconds=60, user_based=True)
def delete_alms_request(name: str) -> None:
	"""Delete one of the member's own benevolence requests before the care team reviews it. Changes data."""
	require_person()
	require_page("alms-request")
	get_own("Alms Request", name, "delete")
	frappe.delete_doc("Alms Request", name)
