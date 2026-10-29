# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.doctype.note_category.note_category import BENEVOLENCE, PASTORAL_ROLES
from churchit.church_people.member_access import pin_to_members_own_person, validate_members_recipient
from churchit.church_scope import refuse_another_churches_parent
from churchit.utils import resolve_link_titles

ALMS_NOTIFICATION = "New Alms Request"
ALMS_SUBJECT = "New alms request: {{ doc.title }}"
ALMS_MESSAGE = """<p>A new alms request was added{% if church_name(doc) %} at {{ church_name(doc) | e }}{% endif %}.</p>

{% set recipient_field = {"Person": "full_name", "Family": "family_name"}.get(doc.recipient_type) %}
<ul>
  <li><strong>For:</strong> {{ (recipient_field and frappe.db.get_value(doc.recipient_type, doc.recipient, recipient_field) or doc.recipient) | e }}</li>
  <li><strong>Requested by:</strong> {{ frappe.db.get_value("Person", doc.requestor, "full_name") | e }}</li>
  {% if doc.amount %}<li><strong>Amount:</strong> {{ frappe.utils.fmt_money(doc.amount) }}</li>{% endif %}
  <li><strong>Status:</strong> {{ doc.status }}</li>
</ul>

<p style="white-space: pre-line">{{ doc.description | e }}</p>

<p><a href="{{ frappe.utils.get_url_to_form(doc.doctype, doc.name) }}">Open the request</a></p>
"""


class AlmsRequest(Document):
	def onload(self):
		# The Case Notes buttons follow the rights on a Benevolence note, not on Person Note.
		# frappe.has_permission, not note.has_permission, which msgprints each refusal into the response.
		note = frappe.new_doc("Person Note", category=BENEVOLENCE, owner=frappe.session.user)
		has_category = bool(frappe.db.exists("Note Category", BENEVOLENCE))
		for key, ptype in (("can_read_case_notes", "read"), ("can_add_case_notes", "create")):
			self.set_onload(key, has_category and frappe.has_permission("Person Note", ptype, note))

	def validate(self):
		# Before the pin: `church` came from the requestor as sent, and the pin does not change it.
		refuse_another_churches_parent(
			self,
			"requestor",
			_("{0} belongs to another church, so only that church can record their alms requests."),
		)
		pin_to_members_own_person(self, "requestor")
		validate_members_recipient(self)

	def before_save(self):
		# Set the alms request title
		recipient_label = self.recipient or ""
		if self.recipient and self.recipient_type:
			meta = frappe.get_meta(self.recipient_type)
			if meta.title_field:
				recipient_label = (
					frappe.db.get_value(self.recipient_type, self.recipient, meta.title_field)
					or self.recipient
				)
		parts = [recipient_label, str(self.amount or ""), self.status or ""]
		self.title = " - ".join(p for p in parts if p)


@frappe.whitelist(methods=["POST"])
def create_expense(alms_request_name: str):
	"""Create the one Expense for the given Alms Request, in the request's church."""
	alms = frappe.get_doc("Alms Request", alms_request_name)
	alms.check_permission("write")
	if frappe.db.get_value("Alms Request", alms.name, "associated_expense", for_update=True):
		frappe.throw(_("This alms request already has an expense."))
	# Make sure an expense type and amount are provided
	if not alms.amount:
		frappe.throw(_("⚠️ An amount is required for an expense to be created."))
	if not alms.expense_type:
		frappe.throw(_("⚠️ An expense type is required for an expense to be created."))
	expense = frappe.new_doc("Expense")
	expense.title = f"Alms: {alms.title}"
	expense.amount = alms.amount
	expense.type = alms.expense_type
	expense.date = frappe.utils.now()
	expense.church = alms.church
	expense.insert()
	expense.submit()
	frappe.db.set_value("Alms Request", alms_request_name, "associated_expense", expense.name)


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
