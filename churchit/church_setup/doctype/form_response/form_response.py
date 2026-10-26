# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, fmt_money

from churchit.church_finances.doctype.collection.collection import add_single_donation
from churchit.church_finances.doctype.online_donation.online_donation import PAID_STATUSES
from churchit.church_finances.payments import (
	PAYMENT_RECORDERS,
	get_payment_url,
	is_charge_confirmed,
	notify_finance,
)
from churchit.church_people.followup import FORM_SUBMITTED, start_cards
from churchit.church_people.matching import find_or_add_person
from churchit.church_scope import refuse_another_churches_parent, session_person
from churchit.questions import get_fields, set_answers

NEW = "New"
PROCESSED = "Processed"
UNPAID, PAID, REFUNDED = "Unpaid", "Paid", "Refunded"
# Only code sets these (`flags.set_by_code`); validate puts back what a browser sent.
PAYMENT_FIELDS = ("amount_paid", "payment_status")
# The Person source of the people a response adds.
FORM = "Form"


class FormResponse(Document):
	"""One answer to a Question Set published as a form, and the person Churchit found or added for it."""

	def validate(self):
		self.restore_payment_fields()
		refuse_another_churches_parent(
			self,
			"question_set",
			_("{0} belongs to another church, so only that church can take its answers."),
		)
		if self.is_new():
			refuse_a_closed_form(self.question_set)
			set_answers(self, self.question_set, {row.question: row.answer for row in self.answers})
			if flt(frappe.db.get_value("Question Set", self.question_set, "price")):
				self.payment_status = UNPAID
			if frappe.flags.in_web_form:
				self.person = session_person()

	def after_insert(self):
		frappe.enqueue_doc(self.doctype, self.name, "process", enqueue_after_commit=True)

	def process(self):
		"""Background job: link or add the response's person and start the Form Submitted workflows, once.

		It runs as whoever sent the response, a guest for the web form, so its writes skip permissions.
		"""
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) != NEW:
			return
		self.reload()

		if not self.person:
			# A shared set has no church, so a guest is matched and added at the church that shared it.
			self.person, _added = find_or_add_person(self.candidate, self.payment_church, FORM)
		self.status = PROCESSED
		self.flags.set_by_code = True
		self.save(ignore_permissions=True)

		# A shared set belongs to no church, so the person's own church follows them up.
		church = self.church or frappe.db.get_value("Person", self.person, "church")
		start_cards(FORM_SUBMITTED, self.person, church, value=self.question_set, source=self)

	def restore_payment_fields(self):
		"""Put back the stored payment fields unless code set them (`flags.set_by_code`)."""
		if self.flags.set_by_code:
			return
		before = self.get_doc_before_save()
		for fieldname in PAYMENT_FIELDS:
			self.set(fieldname, before.get(fieldname) if before else None)

	@property
	def payment_church(self) -> str | None:
		"""The church that takes this response's payment: its Question Set's, or the church that shared it."""
		church, shared_by = frappe.db.get_value(
			"Question Set", self.question_set, ["church", "shared_by_church"]
		)
		return church or shared_by

	def on_payment_authorized(self, status: str | None = None):
		"""The payments app callback (X6.4): record a charge of the set's price once."""
		if status not in PAID_STATUSES:
			return
		frappe.db.get_value(self.doctype, self.name, "name", for_update=True)
		self.reload()
		form = frappe.db.get_value("Question Set", self.question_set, ["price", "fund"], as_dict=True)
		church = self.payment_church
		currency = frappe.get_cached_doc("Giving Settings").currency or "USD"
		# A gateway calls back once for each charge, so a callback on a paid response is a second charge.
		if self.payment_status in (PAID, REFUNDED):
			reason = _(
				"Form response {0} was charged again after it was paid. Refund the extra charge."
			).format(self.name)
		elif not (flt(form.price) and is_charge_confirmed(self, form.price, currency)):
			reason = _(
				"Form response {0} was charged online, but not its price of {1}. Check the payment before you record it."
			).format(self.name, fmt_money(form.price, currency=currency))
		else:
			add_single_donation(
				church, form.fund, form.price, _("Payment for form response {0}").format(self.name)
			)
			self.amount_paid = form.price
			self.payment_status = PAID
			self.flags.set_by_code = True
			self.save(ignore_permissions=True)
			return

		notify_finance([frappe._dict(doctype=self.doctype, name=self.name, church=church)], reason)

	@frappe.whitelist(methods=["POST"])
	def record_refund(self):
		"""Church Finance: the payment was refunded at the processor."""
		frappe.only_for(PAYMENT_RECORDERS)
		self.reload()
		self.check_permission("write")
		if self.payment_status != PAID:
			frappe.throw(_("Only a paid form response can be refunded."))
		self.payment_status = REFUNDED
		self.flags.set_by_code = True
		self.save()

	@property
	def candidate(self) -> dict:
		"""The response as the matcher reads a person."""
		return {
			"first_name": self.first_name,
			"last_name": self.last_name,
			"emails": [self.email] if self.email else [],
			"phones": [],
		}


def refuse_a_closed_form(question_set: str | None) -> None:
	"""Refuse *question_set* unless it is published as a form, and refuse a non-member when it is for members only."""
	form = question_set and frappe.db.get_value(
		"Question Set", question_set, ["publish_as_form", "members_only"], as_dict=True
	)
	# A set that is missing and one that is not published read the same, so a guessed name tells nothing.
	if not (form and form.publish_as_form):
		frappe.throw(_("This form is not open."), frappe.PermissionError)
	if form.members_only and not session_person():
		frappe.throw(_("Please log in as a member to answer this form."), frappe.PermissionError)


@frappe.whitelist(allow_guest=True, methods=["GET"])
@rate_limit(limit=300, seconds=60 * 60)
def get_form(question_set: str | None = None) -> dict:
	"""The title and question fields of *question_set* for the form web form, when it is open to the reader."""
	refuse_a_closed_form(question_set)
	form = frappe.db.get_value("Question Set", question_set, ["title", "price"], as_dict=True)
	return {"title": form.title, "price": flt(form.price), "fields": get_fields(question_set)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def pay(response: str) -> str:
	"""The gateway checkout of a priced form, which the form opens after the save."""
	doc = frappe.get_doc("Form Response", response)
	form = frappe.db.get_value("Question Set", doc.question_set, ["title", "price"], as_dict=True)
	if doc.payment_status in (PAID, REFUNDED):
		frappe.throw(_("This form is already paid."))
	if not flt(form.price):
		frappe.throw(_("This form has nothing to pay."))

	return get_payment_url(
		doc,
		form.price,
		frappe.get_cached_doc("Giving Settings").currency or "USD",
		doc.payment_church,
		form.title,
		_("Payment for {0}").format(form.title),
		payer_name=" ".join(filter(None, (doc.first_name, doc.last_name))) or None,
		payer_email=doc.email or None,
	)
