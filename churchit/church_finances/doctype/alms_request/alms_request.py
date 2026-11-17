# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.doctype.note_category.note_category import BENEVOLENCE, PASTORAL_ROLES
from churchit.church_people.member_access import (
	is_member_only,
	is_portal_member,
	validate_members_recipient,
)
from churchit.church_scope import refuse_another_churches_parent, session_person
from churchit.utils import resolve_link_titles

PENDING = "Pending"
FINANCE_ROLE = "Church Finance"
ALMS_NOTIFICATION = "New Alms Request"
ALMS_SUBJECT = "New alms request: {{ doc.title }}"
ALMS_MESSAGE = """<p>A new alms request was added{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %}.</p>

{% set recipient_field = {"Person": "full_name", "Family": "family_name"}.get(doc.recipient_type) %}
<ul>
  <li><strong>For:</strong> {{ (recipient_field and frappe.db.get_value(doc.recipient_type, doc.recipient, recipient_field) or doc.recipient) | e }}</li>
  <li><strong>Requested by:</strong> {{ frappe.db.get_value("Person", doc.requestor, "full_name") | e }}</li>
  {% if doc.amount %}<li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount, currency=frappe.db.get_default("currency")) }}</li>{% endif %}
  <li><strong>Status:</strong> {{ doc.status }}</li>
</ul>

<p style="white-space: pre-line">{{ doc.description | e }}</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the request</a></p>
"""
APPROVED_NOTIFICATION = "Alms Request Approved"
APPROVED_SUBJECT = "Alms request approved: {{ doc.title }}"
APPROVED_MESSAGE = """<p>An alms request was approved{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %} and waits for its expense.</p>

<ul>
  <li><strong>For:</strong> {{ doc.title | e }}</li>
  {% if doc.amount %}<li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount, currency=frappe.db.get_default("currency")) }}</li>{% endif %}
  {% if doc.expense_type %}<li><strong>Expense type:</strong> {{ doc.expense_type | e }}</li>{% endif %}
</ul>

<p>Open the request and choose Actions, then Create Expense. The request then shows as Distributed.</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the request</a></p>
"""


def is_reviewed(request: Document | dict) -> bool:
	"""True once the care team decided on *request* or it has an expense: then its requester can no longer change it."""
	return request.get("status") != PENDING or bool(request.get("associated_expense"))


def is_paying_expense(expense: str | None) -> bool:
	"""True when *expense* is submitted. A request keeps the link to its cancelled expense, which pays nothing."""
	return bool(expense) and frappe.db.get_value("Expense", expense, "docstatus") == 1


class AlmsRequest(Document):
	def onload(self):
		self.set_onload("is_paid", is_paying_expense(self.associated_expense))

		# The Case Notes buttons follow the rights on a Benevolence note, not on Person Note.
		# frappe.has_permission, not note.has_permission, which msgprints each refusal into the response.
		note = frappe.new_doc("Person Note", category=BENEVOLENCE, owner=frappe.session.user)
		has_category = bool(frappe.db.exists("Note Category", BENEVOLENCE))
		for key, ptype in (("can_read_case_notes", "read"), ("can_add_case_notes", "create")):
			self.set_onload(
				key, has_category and frappe.has_permission("Person Note", ptype, note, throw=False)
			)

	def validate(self):
		# Before the fill: `church` came from the requestor as sent, and the fill does not change it.
		refuse_another_churches_parent(
			self,
			"requestor",
			_("{0} belongs to another church, so only that church can record their alms requests."),
		)
		self.fill_requestor_from_login()
		validate_members_recipient(self)
		self.keep_the_decision_with_the_care_team()

	def before_save(self):
		self.title = get_recipient_name(self.recipient_type, self.recipient)

	def on_trash(self):
		if is_member_only(self.doctype, frappe.session.user) and is_reviewed(self):
			frappe.throw(
				_("The church has reviewed this request, so you cannot delete it."), frappe.PermissionError
			)
		if is_paying_expense(self.associated_expense):
			frappe.throw(
				_("Expense {0} pays this request. Cancel the expense before you delete the request.").format(
					frappe.bold(self.associated_expense)
				)
			)

	def fill_requestor_from_login(self):
		"""The web form does not show Requester: a member always names themselves, and staff fill it when empty.

		Requester is a Person, so a login with no Person cannot send a request, and a Family cannot stand in.
		"""
		if not (is_portal_member() or (frappe.flags.in_web_form and not self.requestor)):
			return
		person = session_person()
		if not person:
			frappe.throw(_("Your login is not linked to a person record. Contact the church office."))
		self.requestor = person

	def keep_the_decision_with_the_care_team(self):
		"""A requester sets no status, and changes the request only until the care team reviews it.

		The web form and REST save a member's own request with their if_owner write right, and the
		portal form sends the status it shows back, so the status is pinned here.
		"""
		if not is_member_only(self.doctype, frappe.session.user):
			return
		before = self.get_doc_before_save()
		if before and is_reviewed(before):
			frappe.throw(
				_(
					"The church has reviewed this request, so you cannot change it. Contact the church office."
				),
				frappe.PermissionError,
			)
		self.status = PENDING


def get_recipient_name(recipient_type: str | None, recipient: str | None) -> str | None:
	"""The recipient's title, such as a person's full name, which is the request's title.

	Anonymizing writes Anonymized over a person's full name in this stored copy.
	"""
	if not recipient or not recipient_type:
		return recipient
	title_field = frappe.get_meta(recipient_type).title_field
	return (title_field and frappe.db.get_value(recipient_type, recipient, title_field)) or recipient


def get_expense_title(alms_request: str) -> str:
	"""The title of the Expense that pays *alms_request*: its ID, never the recipient, whom no Expense links to."""
	return _("Alms Request {0}").format(alms_request)


@frappe.whitelist(methods=["POST"])
def create_expense(alms_request_name: str) -> str:
	"""Create and submit the one Expense for the given Alms Request, in the request's church. Changes data.

	An Approved request becomes Distributed. Returns the Expense's name.
	"""
	alms = frappe.get_doc("Alms Request", alms_request_name)
	alms.check_permission("write")
	linked_expense = frappe.db.get_value("Alms Request", alms.name, "associated_expense", for_update=True)
	if is_paying_expense(linked_expense):
		frappe.throw(_("This alms request already has an expense."))

	if not (alms.amount and alms.amount > 0 and alms.expense_type):
		frappe.throw(_("Enter the Amount and the Expense Type, then click Create Expense."))

	expense = frappe.new_doc("Expense")
	expense.title = get_expense_title(alms.name)
	expense.amount = alms.amount
	expense.type = alms.expense_type
	expense.date = frappe.utils.now()
	expense.church = alms.church
	expense.insert()
	expense.submit()
	values = {"associated_expense": expense.name}
	if alms.status == "Approved":
		values["status"] = "Distributed"
	frappe.db.set_value("Alms Request", alms.name, values)
	return expense.name


def create_new_alms_request_notification() -> None:
	"""Insert the Notification that tells the care team and Church Managers of a new alms request, once.

	It is not standard, because production cannot enable a shipped one, and a church may change it.
	"""
	if frappe.db.exists("Notification", ALMS_NOTIFICATION):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": ALMS_NOTIFICATION,
			"subject": ALMS_SUBJECT,
			"document_type": "Alms Request",
			"event": "New",
			"channel": "Email",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"recipients": [{"receiver_by_role": role} for role in PASTORAL_ROLES],
			"message_type": "HTML",
			"message": ALMS_MESSAGE,
		}
	).insert(ignore_permissions=True)


def create_alms_request_approved_notification() -> None:
	"""Insert the Notification that tells Church Finance an alms request was approved and needs its expense, once.

	The care team approves, but only Finance creates the Expense. It is not standard, for the reasons above.
	"""
	if frappe.db.exists("Notification", APPROVED_NOTIFICATION):
		return
	frappe.get_doc(
		{
			"doctype": "Notification",
			"name": APPROVED_NOTIFICATION,
			"subject": APPROVED_SUBJECT,
			"document_type": "Alms Request",
			"event": "Value Change",
			"value_changed": "status",
			"condition_type": "Python",
			"condition": 'doc.status == "Approved" and not doc.associated_expense',
			"channel": "Email",
			"enabled": 1,
			"is_standard": 0,
			"send_system_notification": 1,
			"recipients": [{"receiver_by_role": FINANCE_ROLE}],
			"message_type": "HTML",
			"message": APPROVED_MESSAGE,
		}
	).insert(ignore_permissions=True)


def get_list_context(context):
	context.filters = {"owner": frappe.session.user}
	context.order_by = "modified desc"

	def get_list(doctype, txt, filters, limit_start, limit_page_length=20, **kwargs):
		from frappe.www.list import get_list as default_get_list

		rows = default_get_list(doctype, txt, filters, limit_start, limit_page_length, **kwargs)
		resolve_link_titles(rows, doctype)
		return rows

	context.get_list = get_list
	return context
