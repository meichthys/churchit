# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import fmt_money, formatdate, now, nowdate

from churchit.contacts import get_primary_email

# Statuses reported by Payments-app gateway controllers that mean the
# payment succeeded. Different gateways use slightly different words.
PAID_STATUSES = ("Authorized", "Completed", "Paid")

# Payment Type used for online gifts (created in after_install / patch).
ONLINE_PAYMENT_TYPE = "Online"


class OnlineDonation(Document):
	def on_payment_authorized(self, status=None):
		"""Callback invoked by the Payments-app gateway controller once the
		donor finishes paying. Records the gift in the Finance module on
		success and returns the URL the donor should land on.

		See ``payments`` gateway controllers, e.g.
		``StripeSettings.finalize_request`` which calls
		``run_method("on_payment_authorized", status)``.
		"""
		if status in PAID_STATUSES:
			if self.status != "Paid":
				self.record_donation()
		else:
			self.db_set("status", "Failed")

		return f"/give?success={self.name}"

	def record_donation(self):
		"""Create and submit a Collection holding this single gift so it flows
		through the existing Fund / report / dashboard logic, then mark this
		record Paid and email a receipt."""
		collection = frappe.new_doc("Collection")
		collection.date = now()
		collection.append(
			"donations",
			{
				"amount": self.amount,
				"payment_type": ONLINE_PAYMENT_TYPE,
				"fund": self.fund,
				# blank person => recorded as an anonymous gift
				"person": self.person or None,
				"notes": self.notes,
			},
		)
		# A single-donation collection balances exactly, so before_submit() passes.
		collection.expected_total = self.amount
		collection.insert(ignore_permissions=True)
		collection.submit()

		self.status = "Paid"
		self.collection = collection.name
		self.save(ignore_permissions=True)

		self.send_acknowledgment()

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
			"amount": fmt_money(self.amount, currency=self.currency),
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
