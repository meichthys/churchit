# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from itertools import groupby

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce
from frappe.utils import flt, fmt_money, formatdate, nowdate

from churchit.church_finances.doctype.collection.collection import add_single_donation
from churchit.church_finances.payments import get_integration_request, is_charge_confirmed, notify_finance
from churchit.church_people import summaries
from churchit.church_scope import refuse_another_churches_record
from churchit.contacts import get_primary_email

# Statuses reported by Payments-app gateway controllers that mean the
# payment succeeded. Different gateways use slightly different words.
PAID_STATUSES = ("Completed", "Paid")
# Doctypes besides gifts that take online payments, each with `payment_status` and `payment_church`.
PAYABLE_DOCTYPES = ("Function Sign-Up", "Form Response")


class OnlineDonation(Document):
	def validate(self):
		refuse_another_churches_record(self, "Fund", self.fund)
		self.refuse_a_changed_collection()
		self.refuse_a_giver_on_a_cancelled_collection()

	def refuse_a_changed_collection(self):
		"""Only record_donation sets the Collection, because a new person rewrites its Donation row."""
		if self.flags.recording_gift or (self.is_new() and not self.collection):
			return
		if self.has_value_changed("collection"):
			frappe.throw(_("An online gift gets its Collection when it is recorded. You cannot change it."))

	def refuse_a_giver_on_a_cancelled_collection(self):
		"""A refunded gift's Donation row is cancelled, so no statement would count the new giver."""
		if not (self.collection and self.has_value_changed("person")):
			return
		if frappe.db.get_value("Collection", self.collection, "docstatus") == 2:
			frappe.throw(_("The collection of this gift is cancelled, so you cannot change its person."))

	def on_update(self):
		if self.collection and self.has_value_changed("person"):
			self.give_donation_to_person()

	@property
	def charged_amount(self) -> float:
		"""The whole payment: the gift and the processing fee the giver chose to cover."""
		return flt(flt(self.amount) + flt(self.fee_amount), self.precision("amount"))

	def on_payment_authorized(self, status=None):
		"""Callback invoked by the Payments-app gateway controller once the
		donor finishes paying. Records the gift in the Finance module on
		success and returns the URL the donor should land on.

		See ``payments`` gateway controllers, e.g.
		``StripeSettings.finalize_request`` which calls
		``run_method("on_payment_authorized", status)``.
		"""
		if status in PAID_STATUSES:
			self.record_charge()
		else:
			self.db_set("status", "Failed")

		return f"/give?success={self.name}"

	@frappe.whitelist(methods=["POST"])
	def record_charged_gift(self):
		"""Record a Pending gift the gateway charged when its callback never arrived."""
		self.reload()
		self.check_permission("write")
		if self.status != "Pending":
			frappe.throw(_("Only a Pending gift can be recorded. This gift is {0}.").format(_(self.status)))
		if not get_integration_request(self):
			frappe.throw(_("No completed payment was found for this gift."))

		self.record_charge()

	def record_charge(self):
		"""Record the gift once, and only when the gateway charged its amount in its currency.

		The checkout page sends the amount from the browser, so the gift's own amount
		is not proof of what the donor paid. The gateway's request log is.
		"""
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) in ("Paid", "Refunded"):
			return

		request = get_integration_request(self)
		if request:
			self.transaction_reference = request.name

		if not is_charge_confirmed(self, self.charged_amount, self.currency):
			self.db_set({"status": "Needs Review", "transaction_reference": self.transaction_reference})
			notify_finance([self], self.get_charge_problem(request))
			return

		self.record_donation()

	def get_charge_problem(self, request) -> str:
		"""Why *request*, the newest completed charge, cannot record this gift."""
		if not request:
			return _("No completed payment was found for online gift {0}.").format(self.name)

		charged = frappe.parse_json(request.data or "{}")
		return _(
			"Online gift {0} was charged {1}, but the gift is {2}. Check the payment before you record it."
		).format(
			self.name,
			fmt_money(charged.get("amount"), currency=charged.get("currency")),
			fmt_money(self.charged_amount, currency=self.currency),
		)

	def record_donation(self):
		"""Create and submit a Collection holding this single gift so it flows
		through the existing Fund / report / dashboard logic, then mark this
		record Paid and email a receipt."""
		self.collection = add_single_donation(
			self.church, self.fund, self.charged_amount, self.notes, person=self.person
		)
		self.status = "Paid"
		self.flags.recording_gift = True
		self.save(ignore_permissions=True)

		self.send_acknowledgment()

	def give_donation_to_person(self):
		"""Name the giver Finance chose on the gift's Donation row, so statements and summaries count it."""
		frappe.db.set_value(
			"Donation",
			{"parent": self.collection, "parenttype": "Collection"},
			{
				"person": self.person,
				"person_email": get_primary_email("Person", self.person) if self.person else None,
			},
		)
		giver = frappe.db.get_value("Person", self.person, "full_name") if self.person else _("nobody")
		frappe.get_doc("Collection", self.collection).add_comment(
			"Info", _("Online gift {0} now names {1} as the giver.").format(self.name, giver)
		)

		before = self.get_doc_before_save() or frappe._dict()
		people = {before.get("person"), self.person} - {None, ""}
		summaries.queue_refresh(people)

	def send_acknowledgment(self):
		"""Email the giver a receipt using the shipped "Donation Acknowledgment"
		Email Template. Best-effort: a mail failure must not undo the recorded
		gift."""
		recipient = self.email
		first_name = (self.donor_name or "").split(" ")[0]
		if self.person:
			person = frappe.db.get_value("Person", self.person, ["first_name"], as_dict=True)
			if person:
				recipient = recipient or get_primary_email("Person", self.person)
				first_name = person.first_name or first_name

		if not recipient:
			return

		context = {
			"first_name": first_name or _("Friend"),
			"amount": fmt_money(self.charged_amount, currency=self.currency),
			"fund": frappe.db.get_value("Fund", self.fund, "fund") or self.fund,
			"date": formatdate(nowdate()),
			"doc": self,
		}

		subject = _("Receipt for your gift")
		message = _("<p>Dear {0},</p><p>Thank you for your gift of {1} to the {2} fund.</p>").format(
			context["first_name"], context["amount"], context["fund"]
		)
		if frappe.db.exists("Email Template", "Donation Acknowledgment"):
			template = frappe.get_doc("Email Template", "Donation Acknowledgment")
			# Render via the framework's own helper so the Jinja evaluation happens
			# inside Frappe core against the normal email template
			formatted = template.get_formatted_email(context)
			subject = formatted["subject"]
			message = formatted["message"]

		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
		except Exception:
			frappe.log_error(
				title="Online giving receipt failed",
				message=frappe.get_traceback(),
			)


def alert_unrecorded_gifts():
	"""Daily: tell Finance about gifts that a gateway charged but that are still Pending.

	A callback that fails stores no transaction reference, so the gift is found
	through the request log that names it.
	"""
	Gift = frappe.qb.DocType("Online Donation")
	Request = frappe.qb.DocType("Integration Request")
	# church-scope: a job over every church; notify_finance alerts only each gift's own church
	gifts = (
		frappe.qb.from_(Gift)
		.join(Request)
		.on(Request.reference_docname == Gift.name)
		.where(
			(Request.reference_doctype == "Online Donation")
			& (Request.status == "Completed")
			& (Gift.status == "Pending")
		)
		.select(Gift.name, Gift.church)
		.distinct()
		.orderby(Gift.church)
		.orderby(Gift.name)
		.run(as_dict=True)
	)

	for _church, rows in groupby(gifts, key=lambda gift: gift.church):
		rows = [frappe._dict(gift, doctype="Online Donation") for gift in rows]
		notify_finance(
			rows,
			_(
				"These online gifts were charged but are still Pending: {0}. Open each one and record it."
			).format(", ".join(gift.name for gift in rows)),
		)

	for doctype in PAYABLE_DOCTYPES:
		alert_unrecorded_payments(doctype)


def alert_unrecorded_payments(doctype: str):
	"""Tell Finance about *doctype* records that a gateway charged but that are still unpaid."""
	Record = frappe.qb.DocType(doctype)
	Request = frappe.qb.DocType("Integration Request")
	# church-scope: a job over every church; notify_finance alerts only each record's payment church
	names = (
		frappe.qb.from_(Record)
		.join(Request)
		.on(Request.reference_docname == Record.name)
		.where(
			(Request.reference_doctype == doctype)
			& (Request.status == "Completed")
			& Coalesce(Record.payment_status, "").isin(("", "Unpaid"))
		)
		.select(Record.name)
		.distinct()
		.run(pluck=True)
	)
	records = sorted(
		(
			frappe._dict(doctype=doctype, name=name, church=frappe.get_doc(doctype, name).payment_church)
			for name in names
		),
		key=lambda row: (row.church or "", row.name),
	)
	for _church, rows in groupby(records, key=lambda row: row.church):
		rows = list(rows)
		notify_finance(
			rows,
			_(
				"These were charged online but are still unpaid: {0}. Check each payment, then record it or refund it."
			).format(", ".join(row.name for row in rows)),
		)
