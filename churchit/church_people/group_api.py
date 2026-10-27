# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, get_url, sbool

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL, SMS
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	GROUP_MESSAGES,
)
from churchit.church_communications.sending import can_send_texts, send
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_people.doctype.group_join_request.group_join_request import APPROVED, DENIED, REQUESTED
from churchit.church_people.group_leaders import get_leaders, require_leader
from churchit.church_people.group_meetings import get_roster
from churchit.church_scope import church_filters, session_church, session_person

JOIN_REQUEST_TEMPLATE = "Group Join Request"
JOIN_DECISION_TEMPLATE = "Group Join Decision"
MESSAGE_TEMPLATE = "Group Message"
# A text carries no subject. The leader's words are a placeholder value, never template source.
MESSAGE_TEXT = "{{ leader_name }}: {{ message }}"


def _session_person():
	"""Return the Person doc-name linked to the current session user, or None."""
	return session_person()


@frappe.whitelist()
def joinable_public_groups():
	"""Return the public, portal-visible groups open to join that the current user isn't already a member of.

	`requires_approval` marks a group whose leaders decide, and `requested` one the user already asked to join.
	"""
	person = _session_person()
	mine = (
		{
			r.parent
			for r in frappe.get_all("Group Member", {"person": person, "parenttype": "Group"}, ["parent"])
		}
		if person
		else set()
	)
	# church-scope: the session's own requests
	requested = set(
		frappe.get_all("Group Join Request", {"person": person, "status": REQUESTED}, pluck="group")
		if person
		else ()
	)
	rows = frappe.get_all(
		"Group",
		filters=church_filters(session_church(), public=1, show_in_portal=1),
		fields=["name", "group_name", "description", "requires_approval"],
		order_by="group_name",
	)
	return [
		frappe._dict(r, requested=r.name in requested)
		for r in rows
		if r.name not in mine and frappe.get_doc("Group", r.name).is_enrollment_open
	]


@frappe.whitelist(methods=["POST"])
def join_group(group: str | None, message: str | None = None):
	"""Add the current session user's linked Person to a public group, or ask its leaders to.

	The group must be public, shown in the portal and open (`Group.is_enrollment_open`); the user must
	already have a linked Person record. A group that requires approval gets a Group Join Request, and
	a second call returns the open one with `requested`.
	"""
	group_name = get_portal_group_name(group)
	person = _session_person()
	if not person:
		frappe.throw(
			_(
				"Your user account isn't linked to a Person record yet. "
				"Ask a church administrator to link you."
			)
		)

	# A second call for the same group waits here, then finds the member or the request this one adds.
	doc = frappe.get_doc("Group", group, for_update=True)
	if any(member.person == person for member in doc.members):
		return {"already_member": True, "group_name": group_name}
	if doc.requires_approval:
		return {"requested": True, "request": request_to_join(doc, person, message), "group_name": group_name}

	refuse_a_closed_group(doc)
	add_member(doc, person)
	return {"joined": True, "group_name": group_name}


def get_portal_group_name(group: str | None) -> str:
	"""The name of *group*, when it is a public portal group of the session's church."""
	if not group:
		frappe.throw(_("Group is required."))

	# Only the groups joinable_public_groups offers: another church's group reads as missing.
	row = frappe.db.get_value(
		"Group",
		church_filters(session_church(), name=group),
		["public", "show_in_portal", "group_name"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Group not found."))
	if not row.show_in_portal:
		frappe.throw(_("This group is not available on the portal."))
	if not row.public:
		frappe.throw(_("This group is not public. Ask the group leader to add you."))
	return row.group_name


def request_to_join(group: Document, person: str, message: str | None) -> str:
	"""The open request of *person* for the locked *group*, made and sent to its leaders when there is none."""
	# A locking read: a plain one answers from before the Group lock was taken.
	open_request = frappe.db.get_value(
		"Group Join Request", {"group": group.name, "person": person, "status": REQUESTED}, for_update=True
	)
	if open_request:
		return open_request

	refuse_a_closed_group(group)
	request = frappe.get_doc(
		{"doctype": "Group Join Request", "group": group.name, "person": person, "message": message}
	).insert(ignore_permissions=True)
	if not can_send_email():
		return request.name

	send(
		get_leaders(group.name),
		EMAIL,
		GROUP_MESSAGES,
		request,
		key="request",
		template=JOIN_REQUEST_TEMPLATE,
		context={
			"group_name": group.group_name,
			"person_name": request.person_name,
			"message": request.message or "",
			"link": get_url(f"/group-leader?group={group.name}"),
		},
	)
	return request.name


def refuse_a_closed_group(group: Document) -> None:
	if group.is_enrollment_open:
		return
	if group.is_full:
		frappe.throw(_("{0} is full.").format(group.group_name))
	frappe.throw(_("{0} is closed to new members.").format(group.group_name))


def add_member(group: Document, person: str) -> None:
	"""Add *person* to the locked *group* with the Member role. Group.validate checks its requirements."""
	member_role = frappe.db.get_value("Group Role", {"role": "Member"}, "name")
	group.append("members", {"person": person, "group_role": member_role})
	group.save(ignore_permissions=True)


def get_open_join_requests(groups: list[str]) -> dict[str, list[dict]]:
	"""{group: its Requested join requests, oldest first} of *groups*, for the leader page's Approve and Deny buttons."""
	requests = {group: [] for group in groups}
	if not groups:
		return requests
	# church-scope: the requests of the groups the leader page found the session's Person leads
	for row in frappe.get_all(
		"Group Join Request",
		filters={"group": ("in", groups), "status": REQUESTED},
		fields=["name", "group", "person_name", "message", "creation"],
		order_by="creation asc",
	):
		requests[row.group].append(row)
	return requests


@frappe.whitelist(methods=["POST"])
def decide_join_request(request: str, approve: bool | str) -> dict:
	"""Approve or deny a Requested join request, for a leader of its group or a user who may edit the group.

	Approval adds the person to the group. Either way the person gets one email, when the site can send one.
	"""
	group = frappe.db.get_value("Group Join Request", request, "group")
	# A request that does not exist is refused like one the user may not decide.
	if not (group and frappe.has_permission("Group", "write", doc=group)):
		require_leader(group)

	# The Group first, as join_group locks it, so a decision and a join cannot deadlock.
	group_doc = frappe.get_doc("Group", group, for_update=True)
	doc = frappe.get_doc("Group Join Request", request, for_update=True)
	if doc.status != REQUESTED:
		frappe.throw(_("This request was already decided: {0}.").format(_(doc.status)))

	approved = sbool(approve)
	if approved and not any(member.person == doc.person for member in group_doc.members):
		if group_doc.is_full:
			frappe.throw(
				_("{0} is full. Raise its capacity, or deny the request.").format(group_doc.group_name)
			)
		add_member(group_doc, doc.person)
	doc.status = APPROVED if approved else DENIED
	doc.decided_by = frappe.session.user
	doc.save(ignore_permissions=True)
	if not can_send_email():
		return {"status": doc.status}

	send(
		[doc.person],
		EMAIL,
		GROUP_MESSAGES,
		doc,
		key="decision",
		template=JOIN_DECISION_TEMPLATE,
		context={"group_name": group_doc.group_name, "approved": approved, "link": get_url("/groups")},
	)
	return {"status": doc.status}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def message_group(group: str, subject: str, message: str, channel: str = EMAIL) -> int:
	"""Leader page: send *message* to the living members of a group the session user leads.

	Each message gets its own send key, the Comment's name, so the same words sent twice both go out.
	Returns the number of people it reached.
	"""
	leader = require_leader(group)
	if not (subject or "").strip() or not (message or "").strip():
		frappe.throw(_("Write a subject and a message."))
	if channel not in (EMAIL, SMS):
		frappe.throw(_("A group message goes by {0} or {1}.").format(EMAIL, SMS))
	if channel == SMS and not can_send_texts():
		frappe.throw(_("This site cannot send texts."))
	if channel == EMAIL and not can_send_email():
		frappe.throw(_("This site cannot send email yet. Ask the church office."))

	group_doc = frappe.get_doc("Group", group)
	leader_name = frappe.db.get_value("Person", leader, "full_name")
	comment = group_doc.add_comment(
		"Info",
		_("{0} sent the group a message: {1}").format(escape_html(leader_name), escape_html(subject)),
	)
	members = [person.name for person in get_roster(group)]
	context = {
		"subject": subject,
		"message": message,
		"leader_name": leader_name,
		"group_name": group_doc.group_name,
	}
	if channel != SMS:
		return len(
			send(
				members,
				channel,
				GROUP_MESSAGES,
				group_doc,
				key=comment.name,
				template=MESSAGE_TEMPLATE,
				context=context,
			)
		)

	reached = 0
	for member in members:
		# A text leaves at once, so each copy is committed as soon as it is sent.
		reached += len(
			send(
				[member], SMS, GROUP_MESSAGES, group_doc, key=comment.name, text=MESSAGE_TEXT, context=context
			)
		)
		frappe.db.commit()
	return reached
