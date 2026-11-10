from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.bank_transaction.bank_transaction import match_transaction
from churchit.church_finances.doctype.donation.donation import Donation
from churchit.church_finances.doctype.fund.fund import get_or_create_missionary_fund
from churchit.church_finances.doctype.missionary_payment.missionary_payment import mark_as_sent, reconcile
from churchit.church_finances.doctype.missionary_support_summary.missionary_support_summary import (
	generate_990_summary,
)
from churchit.church_missions.doctype.missionary.missionary import Missionary
from churchit.church_missions.doctype.missionary_support_schedule.missionary_support_schedule import (
	MissionarySupportSchedule,
	send_variance_alert,
)


class TestMissionaryPayment(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.missionary = frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Payment Missionary",
				"church": frappe.db.get_value("Church", {"is_root": 1}, "name") or "CHR-ROOT",
			}
		).insert(ignore_permissions=True)
		self.fund = get_or_create_missionary_fund(self.missionary.name)

	def test_auto_creation_on_donation_save(self):
		"""A donation with missionary set and Paid status auto-creates a Missionary Payment."""
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 250.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		self.assertEqual(len(payments), 1)

		payment = frappe.get_doc("Missionary Payment", payments[0].name)
		self.assertEqual(payment.amount, 250.00)
		self.assertEqual(payment.missionary, self.missionary.name)
		self.assertEqual(payment.status, "Scheduled")

	def test_duplicate_prevention(self):
		"""Saving donation multiple times does not create duplicate Missionary Payments."""
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 100.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)

		donation.save(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		self.assertEqual(len(payments), 1)

	def test_workflow_state_transitions_and_fields(self):
		"""Test workflow state transitions and field auto-population for Sent and Reconciled."""
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 150.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		payment_name = payments[0].name

		# Mark as Sent using server method
		mark_as_sent(payment_name, "CHK-12345")
		payment = frappe.get_doc("Missionary Payment", payment_name)
		self.assertEqual(payment.status, "Sent")
		self.assertEqual(payment.reference, "CHK-12345")
		self.assertEqual(payment.sent_by, frappe.session.user)
		self.assertIsNotNone(payment.sent_date)

		# Reconcile using server method (creates Bank Transaction and links)
		reconcile(payment_name, "BANK-9999")
		payment.reload()
		self.assertEqual(payment.status, "Reconciled")
		self.assertEqual(payment.reference, "BANK-9999")
		self.assertEqual(payment.reconciled_by, frappe.session.user)
		self.assertIsNotNone(payment.reconciled_date)
		self.assertTrue(payment.bank_transaction)

		txn = frappe.get_doc("Bank Transaction", payment.bank_transaction)
		self.assertEqual(txn.status, "Matched")
		self.assertEqual(txn.matched_payment, payment.name)

	def test_bank_transaction_matching(self):
		"""Matching an unmatched bank transaction to a sent payment updates both statuses."""
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 200.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		payment_name = payments[0].name
		mark_as_sent(payment_name, "WIRE-555")

		txn = frappe.get_doc(
			{
				"doctype": "Bank Transaction",
				"date": frappe.utils.today(),
				"amount": 200.00,
				"type": "Outflow",
				"status": "Unmatched",
				"bank_reference": "WIRE-555",
			}
		).insert(ignore_permissions=True)

		match_transaction(txn.name, payment_name)

		txn.reload()
		payment = frappe.get_doc("Missionary Payment", payment_name)
		self.assertEqual(txn.status, "Matched")
		self.assertEqual(txn.matched_payment, payment_name)
		self.assertEqual(payment.status, "Reconciled")
		self.assertEqual(payment.bank_transaction, txn.name)

	def test_support_schedule_variance_and_recalculation(self):
		"""Support schedule recalculation produces correct values and threshold triggers flag."""
		schedule = frappe.get_doc(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary.name,
				"monthly_amount": 100.00,
				"start_date": "2026-01-01",
				"end_date": "2026-03-31",
				"status": "Active",
				"variance_threshold": 10,
			}
		).insert(ignore_permissions=True)

		# Total committed for 3 months = 300. Disbursed = 0 -> variance = 300 (100% variance) -> flagged = 1
		self.assertEqual(schedule.total_committed, 300.0)
		self.assertEqual(schedule.total_disbursed, 0.0)
		self.assertEqual(schedule.variance, 300.0)
		self.assertEqual(schedule.variance_flagged, 1)

		# Add a sent payment of 280 (variance = 20, which is 6.67% < 10% threshold -> flagged = 0)
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 280.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)
		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		mark_as_sent(payments[0].name, "PAY-1")

		schedule.recalculate()
		self.assertEqual(schedule.total_disbursed, 280.0)
		self.assertEqual(schedule.variance, 20.0)
		self.assertEqual(schedule.variance_flagged, 0)

	def test_variance_alert_notification(self):
		"""Mock frappe.sendmail for variance alert test."""
		schedule = frappe.get_doc(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary.name,
				"monthly_amount": 100.00,
				"start_date": "2026-01-01",
				"end_date": "2026-03-31",
				"status": "Active",
			}
		).insert(ignore_permissions=True)

		with patch("frappe.sendmail") as mock_sendmail:
			send_variance_alert(schedule)
			mock_sendmail.assert_called_once()
			args, kwargs = mock_sendmail.call_args
			self.assertIn("Variance alert", kwargs.get("subject", ""))

	def test_generate_990_summary_idempotent(self):
		"""generate_990_summary creates correct records and is idempotent on re-run."""
		donation = frappe.get_doc(
			{
				"doctype": "Donation",
				"fund": self.fund,
				"missionary": self.missionary.name,
				"amount": 500.00,
				"currency": "USD",
				"status": "Paid",
			}
		).insert(ignore_permissions=True)
		# Ensure collection date is in 2026
		collection_name = donation.parent
		frappe.db.set_value("Collection", collection_name, "date", "2026-06-15")

		payments = frappe.get_all("Missionary Payment", filters={"donation": donation.name})
		mark_as_sent(payments[0].name, "990-PAY")
		frappe.db.set_value("Missionary Payment", payments[0].name, "payment_date", "2026-06-20")

		# Run generate_990_summary for year 2026
		generate_990_summary(2026)

		summaries = frappe.get_all(
			"Missionary Support Summary",
			filters={"year": 2026, "missionary": self.missionary.name},
			fields=["name", "total_donations", "total_disbursed", "retained"],
		)
		self.assertEqual(len(summaries), 1)
		self.assertEqual(summaries[0].total_donations, 500.0)
		self.assertEqual(summaries[0].total_disbursed, 150.0)
		self.assertEqual(summaries[0].retained, 350.0)

		# Re-run to test idempotency
		generate_990_summary(2026)
		summaries_after = frappe.get_all(
			"Missionary Support Summary", filters={"year": 2026, "missionary": self.missionary.name}
		)
		self.assertEqual(len(summaries_after), 1)
