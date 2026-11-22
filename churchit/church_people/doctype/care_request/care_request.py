# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
import frappe.share
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate

from churchit.church_people.doctype.note_category.note_category import PASTORAL_ROLES
from churchit.church_people.member_access import is_portal_member
from churchit.church_people.summaries.care import FINISHED
from churchit.church_scope import has_church_access, refuse_another_churches_parent
from churchit.portal.realtime import notify

# Days from the request, or from a change of urgency, to its due date.
URGENCY_DAYS = {"Urgent": 1, "High": 3, "Medium": 7, "Low": 14}
CARE_NOTIFICATION = "New Care Request"
# A caregiver with a desk login gets the request on their To Do list, and that assignment emails them.
CARE_CONDITION = "not doc.caregiver_user"
CARE_SUBJECT = "New care request: {{ doc.category }} for {{ doc.person_name }}"
CARE_MESSAGE = """<p>A new care request was added{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %}.</p>

<ul>
  <li><strong>For:</strong> {{ doc.person_name | e }}</li>
  <li><strong>Category:</strong> {{ doc.category | e }}</li>
  <li><strong>Urgency:</strong> {{ doc.urgency }}</li>
  {% if doc.due_on %}<li><strong>Due:</strong> {{ frappe.utils.format_date(doc.due_on, "EEEE, MMMM d, yyyy") }}</li>{% endif %}
  {% if doc.preferred_contact %}<li><strong>Preferred contact:</strong> {{ doc.preferred_contact }}</li>{% endif %}
  <li><strong>Caregiver:</strong> {% if doc.caregiver %}{{ frappe.db.get_value("Person", doc.caregiver, "full_name") | e }}{% else %}None yet. Choose one on the request.{% endif %}</li>
</ul>

<p style="white-space: pre-line">{{ doc.description | e }}</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the request</a></p>
"""


class CareRequest(Document):
	"""A member's ask for practical help, due by its urgency and on its caregiver's To Do list."""

	def before_insert(self):
		# Frappe fetched the links before this runs, so the member's own person gets its name here too.
		if not self.person and frappe.session.user != "Guest":
			person = frappe.db.get_value("Person", {"user": frappe.session.user}, ["name", "full_name"])
			if person:
				self.person, self.person_name = person
		# An empty urgency or status takes the doctype's default.
		self.urgency = self.urgency or self.meta.get_field("urgency").default
		self.status = self.status or self.meta.get_field("status").default

	def validate(self):
		changed = self.is_new() or self.has_value_changed("submitted_on") or self.has_value_changed("due_on")
		if (
			changed
			and self.submitted_on
			and self.due_on
			and getdate(self.due_on) < getdate(self.submitted_on)
		):
			frappe.throw(_("Due On cannot be before Submitted On."))
		refuse_another_churches_parent(
			self,
			"person",
			_("{0} belongs to another church, so only that church can record care requests for them."),
		)
		if is_portal_member() or self.flags.from_member_app:
			# A member's save never carries the status; only the care team changes it in the desk.
			before = self.get_doc_before_save()
			self.status = before.status if before else self.meta.get_field("status").default

	def before_save(self):
		# If Caregiver is not set, pre-fill it from the person's current
		# care assignment (mirrors the client-side helper for non-portal entry).
		if self.person and not self.caregiver:
			self.caregiver = _current_deacon(self.person)
		self.set_due_date()
		if self.is_handed_over:
			self.refuse_a_caregiver_outside_the_church()

	def on_update(self):
		if self.has_value_changed("status") and not self.flags.in_insert:
			notify(self.owner, "care", self.name)

		if self.status in FINISHED:
			if self.has_value_changed("status"):
				assign_to.close_all_assignments(self.doctype, self.name, ignore_permissions=True)
		elif self.is_handed_over:
			self.hand_to_caregiver()
		elif self.has_value_changed("due_on"):
			frappe.db.set_value(
				"ToDo",
				{"reference_type": self.doctype, "reference_name": self.name, "status": "Open"},
				"date",
				self.due_on,
			)

	@property
	def is_handed_over(self) -> bool:
		"""True when an open request has a new caregiver, or was just reopened."""
		previous = self.get_doc_before_save()
		is_reopened = bool(previous) and previous.status in FINISHED
		return self.status not in FINISHED and (self.has_value_changed("caregiver") or is_reopened)

	@property
	def caregiver_user(self) -> str | None:
		"""The caregiver's enabled desk login, or None."""
		user = self.caregiver and frappe.db.get_value("Person", self.caregiver, "user")
		login = user and frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
		return user if login and login.enabled and login.user_type == "System User" else None

	@property
	def caregiver_name(self) -> str:
		return frappe.db.get_value("Person", self.caregiver, "full_name") or self.caregiver

	def set_due_date(self):
		"""Due by the urgency: counted from the day it was submitted, or from today when the urgency changes."""
		days = URGENCY_DAYS.get(self.urgency)
		if days is None:
			return
		if self.is_new():
			self.due_on = self.due_on or add_days(self.submitted_on or nowdate(), days)
		elif self.has_value_changed("urgency") and not self.has_value_changed("due_on"):
			self.due_on = add_days(nowdate(), days)

	def refuse_a_caregiver_outside_the_church(self):
		"""Refuse before Frappe's DocShare guard would, with a message that says what to do."""
		user = self.caregiver_user
		if user and not has_church_access(user, self.church):
			church_name = frappe.db.get_value("Church", self.church, "church_name")
			frappe.throw(
				_(
					"{0} cannot see the care requests of {1}, so they cannot be the caregiver. Choose someone from {1}."
				).format(frappe.bold(self.caregiver_name), frappe.bold(church_name)),
				title=_("Caregiver outside the church"),
			)

	def hand_to_caregiver(self):
		"""Move the request from the previous caregiver's To Do list to the new caregiver's."""
		previous = self.get_doc_before_save()
		if previous and previous.caregiver and previous.caregiver != self.caregiver:
			previous_user = frappe.db.get_value("Person", previous.caregiver, "user")
			if previous_user:
				assign_to._remove(self.doctype, self.name, previous_user, ignore_permissions=True)

		if not self.caregiver:
			return
		user = self.caregiver_user
		if user:
			self.assign(user)
		elif frappe.get_cached_value("User", frappe.session.user, "user_type") == "System User":
			frappe.msgprint(
				_(
					"{0} has no desk login, so this request is not on their To Do list and they were not told. Let them know yourself."
				).format(frappe.bold(self.caregiver_name)),
				indicator="orange",
			)

	def assign(self, user: str):
		"""Put the request on *user*'s To Do list, dated when it is due; Frappe sends them a notice."""
		# Frappe shares a record with an assignee who cannot read it, but only when the
		# person assigning may share it. Setting the caregiver is that decision here,
		# so the share is made for a care team member or a portal member too.
		if not frappe.has_permission(self.doctype, "read", doc=self, user=user):
			frappe.share.add_docshare(self.doctype, self.name, user, flags={"ignore_share_permission": True})
		person_name = frappe.db.get_value("Person", self.person, "full_name")
		assign_to._add(
			{
				"assign_to": [user],
				"doctype": self.doctype,
				"name": self.name,
				"date": self.due_on,
				"description": _("{0} for {1}").format(self.category, person_name),
			},
			ignore_permissions=True,
		)


def _current_deacon(person):
	"""Return the deacon from the person's current care assignment, if any."""
	today = frappe.utils.nowdate()
	# An open-ended assignment (no end date) or one that has not yet ended.
	for filters in (
		{"person": person, "start_date": ["<=", today], "end_date": ["is", "not set"]},
		{"person": person, "start_date": ["<=", today], "end_date": [">=", today]},
	):
		deacon = frappe.db.get_value("Care Assignment", filters, "deacon", order_by="start_date desc")
		if deacon:
			return deacon
	return None


def create_new_care_request_notification() -> None:
	"""Insert the Notification that tells the care team and Church Managers of a new care request, once.

	It goes out only for a request that no caregiver gets on their To Do list, which would otherwise reach
	no one. It is not standard, because production cannot enable a shipped one, and a church may change it.
	"""
	if frappe.db.exists("Notification", CARE_NOTIFICATION):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": CARE_NOTIFICATION,
			"subject": CARE_SUBJECT,
			"document_type": "Care Request",
			"event": "New",
			"channel": "Email",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"condition": CARE_CONDITION,
			"condition_type": "Python",
			"recipients": [{"receiver_by_role": role} for role in PASTORAL_ROLES],
			"message_type": "HTML",
			"message": CARE_MESSAGE,
		}
	).insert(ignore_permissions=True)
