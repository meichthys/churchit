import frappe
from frappe.tests.utils import FrappeTestCase
from churchit.church_finances.doctype.donation.donation import Donation
from churchit.church_finances.doctype.fund.fund import get_or_create_missionary_fund
from churchit.church_missions.doctype.missionary.missionary import Missionary
from churchit.church_finances.doctype.missionary_payment.missionary_payment import mark_as_sent, reconcile


class TestMissionaryPayment(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.missionary = frappe.get_doc({
			"doctype": "Missionary",
			"title": "_Test Payment Missionary",
			"church": frappe.db.get_value("Church", {"is_root": 1}, "name") or "CHR-ROOT"
		}).insert(ignore_permissions=True)
		self.fund = get_or_create_missionary_fund(self.missionary.name)

	def test_auto_creation_on_donation_save(self):
		"""A donation with missionary set and Paid status auto-creates a Missionary Payment."""
		donation = frappe.get_doc({
			"doctype": "Donation",
			"fund": self.fund,
			"missionary": self.missionary.name,
			"amount": 250.00,
			"currency": "USD",
			"status": "Paid"
		}).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		self.assertEqual(len(payments), 1)

		payment = frappe.get_doc("Missionary Payment", payments[0].name)
		self.assertEqual(payment.amount, 250.00)
		self.assertEqual(payment.missionary, self.missionary.name)
		self.assertEqual(payment.status, "Scheduled")

	def test_duplicate_prevention(self):
		"""Saving donation multiple times does not create duplicate Missionary Payments."""
		donation = frappe.get_doc({
			"doctype": "Donation",
			"fund": self.fund,
			"missionary": self.missionary.name,
			"amount": 100.00,
			"currency": "USD",
			"status": "Paid"
		}).insert(ignore_permissions=True)

		# Save again
		donation.save(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		self.assertEqual(len(payments), 1)

	def test_workflow_state_transitions_and_fields(self):
		"""Test workflow state transitions and field auto-population for Sent and Reconciled."""
		donation = frappe.get_doc({
			"doctype": "Donation",
			"fund": self.fund,
			"missionary": self.missionary.name,
			"amount": 150.00,
			"currency": "USD",
			"status": "Paid"
		}).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		payment_name = payments[0].name

		# Mark as Sent using server method
		mark_as_sent(payment_name, "CHK-12345")
		payment = frappe.get_doc("Missionary Payment", payment_name)
		self.assertEqual(payment.status, "Sent")
		self.assertEqual(payment.reference, "CHK-12345")
		self.assertEqual(payment.sent_by, frappe.session.user)
		self.assertIsNotNone(payment.sent_date)

		# Reconcile using server method
		reconcile(payment_name, "BANK-9999")
		payment.reload()
		self.assertEqual(payment.status, "Reconciled")
		self.assertEqual(payment.reference, "BANK-9999")
		self.assertEqual(payment.reconciled_by, frappe.session.user)
		self.assertIsNotNone(payment.reconciled_date)
