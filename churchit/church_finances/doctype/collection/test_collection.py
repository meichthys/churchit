# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_months, get_datetime, getdate, now

from churchit.church_finances.doctype.collection.collection import ONLINE_PAYMENT_TYPE
from churchit.church_finances.doctype.online_donation import online_donation
from churchit.church_finances.report.fund_transactions_by_date import fund_transactions_by_date
from churchit.patches.v1_0 import date_collection_ledger_rows
from churchit.tests.helpers import RollbackEachTest, make_person


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestCollection(FrappeTestCase):
	def setUp(self):
		self.fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Collection Fund"})
			.insert(ignore_permissions=True)
			.name
		)
		self.payment_type = _ensure("Payment Type", {"type": "Cash"}, {"type": "Cash"})

	def _make_collection(self, amount=200, expected_total=None, date=None):
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": date or now(),
				"expected_total": amount if expected_total is None else expected_total,
			}
		)
		collection.append(
			"donations",
			{"payment_type": self.payment_type, "fund": self.fund, "amount": amount},
		)
		return collection.insert(ignore_permissions=True)

	def test_totals_and_breakdowns_computed(self):
		collection = self._make_collection(amount=200)
		self.assertEqual(collection.total_amount, 200)
		self.assertEqual(collection.imbalance, 0)
		self.assertEqual({f.fund: f.total for f in collection.fund_totals}, {self.fund: 200})
		self.assertEqual(
			{p.payment_type: p.total for p in collection.payment_type_totals},
			{self.payment_type: 200},
		)

	def test_imbalance_computed_from_expected_total(self):
		collection = self._make_collection(amount=200, expected_total=250)
		self.assertEqual(collection.imbalance, -50)

	def test_imbalance_blocks_submit(self):
		collection = self._make_collection(amount=200, expected_total=250)
		with self.assertRaises(ValidationError):
			collection.submit()

	def test_submit_increases_fund_balance(self):
		self._make_collection(amount=200).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)

	def test_cancel_reverses_fund_balance(self):
		collection = self._make_collection(amount=200)
		collection.submit()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 200)
		collection.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.fund, "balance"), 0)

	def ledger(self, **filters):
		rows = frappe.get_all(
			"Financial Transaction",
			{"parenttype": "Fund", **filters},
			["parent", "amount"],
			order_by="parent",
		)
		return [(row.parent, row.amount) for row in rows]

	def test_each_fund_gets_one_ledger_row_and_no_version(self):
		second = frappe.get_doc({"doctype": "Fund", "fund": "_Test Collection Second Fund"}).insert(
			ignore_permissions=True
		)
		funds = (self.fund, second.name)
		versions = {
			fund: frappe.db.count("Version", {"ref_doctype": "Fund", "docname": fund}) for fund in funds
		}
		self._make_collection(amount=7).submit()
		collection = frappe.get_doc({"doctype": "Collection", "date": now(), "expected_total": 180})
		for fund, amount in ((self.fund, 100), (second.name, 30), (self.fund, 50)):
			collection.append(
				"donations", {"payment_type": self.payment_type, "fund": fund, "amount": amount}
			)
		collection.insert(ignore_permissions=True).submit()

		self.assertEqual(self.ledger(source=collection.name), sorted([(self.fund, 150), (second.name, 30)]))
		for fund in funds:
			self.assertEqual(
				frappe.db.count("Version", {"ref_doctype": "Fund", "docname": fund}), versions[fund]
			)
			self.assertEqual(
				frappe.db.get_value("Fund", fund, "balance"),
				sum(amount for _fund, amount in self.ledger(parent=fund)),
			)

		collection.cancel()
		self.assertEqual(self.ledger(source=collection.name), [])
		self.assertEqual(self.ledger(parent=self.fund), [(self.fund, 7)])
		self.assertEqual([frappe.db.get_value("Fund", fund, "balance") for fund in funds], [7, 0])

	def ledger_dates(self, from_date, to_date):
		filters = {"from_date": from_date, "to_date": to_date}
		return [row.date for row in fund_transactions_by_date.execute(filters)[1] if row.amount == 321]

	def test_a_collection_entered_late_shows_in_its_own_month(self):
		last_month = add_months(getdate(), -1).replace(day=15)
		self._make_collection(amount=321, date=f"{last_month} 10:00:00").submit()

		self.assertEqual(self.ledger_dates(last_month, last_month), [get_datetime(f"{last_month} 10:00:00")])
		self.assertEqual(self.ledger_dates(getdate(), getdate()), [])

	def test_the_patch_dates_old_ledger_rows_from_their_collection(self):
		collection = self._make_collection(amount=321, date="2030-04-04 09:30:00")
		collection.submit()
		row = frappe.db.get_value(
			"Financial Transaction", {"source_type": "Collection", "source": collection.name}, "name"
		)
		frappe.db.set_value("Financial Transaction", row, "date", now())

		date_collection_ledger_rows.execute()
		self.assertEqual(
			frappe.db.get_value("Financial Transaction", row, "date"), get_datetime("2030-04-04 09:30:00")
		)

		with patch.object(frappe.db, "set_value") as set_value:
			date_collection_ledger_rows.execute()
		set_value.assert_not_called()


class TestRefund(RollbackEachTest):
	"""A refund at the processor is recorded by cancelling the gift's Collection, or by a negative row."""

	def setUp(self):
		super().setUp()
		self.giver = make_person("_Test Refund", "Giver")
		self.fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Refund Fund"}).insert(
			ignore_permissions=True
		)
		self.payment_type = _ensure("Payment Type", {"type": "Cash"}, {"type": "Cash"})

	def make_collection(self, date, amount):
		"""A submitted Collection with one gift of *amount* from the giver."""
		collection = frappe.get_doc({"doctype": "Collection", "date": date, "expected_total": amount})
		collection.append(
			"donations",
			{
				"person": self.giver.name,
				"fund": self.fund.name,
				"payment_type": self.payment_type,
				"amount": amount,
			},
		)
		collection.insert(ignore_permissions=True).submit()
		return collection

	def gift(self, collection=None, status="Paid"):
		gift = frappe.get_doc(
			{
				"doctype": "Online Donation",
				"amount": 40,
				"fund": self.fund.name,
				"currency": "USD",
				"status": status,
			}
		).insert(ignore_permissions=True)
		# Only recording a gift sets its Collection, so the test sets it under the form.
		if collection:
			gift.db_set("collection", collection.name)
		return gift

	def status(self, gift):
		return frappe.db.get_value("Online Donation", gift.name, "status")

	def test_cancelling_a_gifts_collection_refunds_the_gift(self):
		collection = self.make_collection("2031-03-01", 40)
		gift, pending = self.gift(collection), self.gift(collection, status="Pending")

		collection.cancel()

		self.assertEqual((self.status(gift), self.status(pending)), ("Refunded", "Pending"))
		self.assertFalse(frappe.db.exists("Financial Transaction", {"source": collection.name}))

	def test_a_second_callback_on_a_refunded_gift_records_nothing(self):
		_ensure(
			"Payment Type",
			{"type": ONLINE_PAYMENT_TYPE},
			{"type": ONLINE_PAYMENT_TYPE},
		)
		gift = self.gift(status="Pending")
		with (
			patch.object(online_donation, "is_charge_confirmed", return_value=True),
			patch.object(online_donation.OnlineDonation, "send_acknowledgment"),
		):
			gift.on_payment_authorized("Completed")
			frappe.get_doc(
				"Collection", frappe.db.get_value("Online Donation", gift.name, "collection")
			).cancel()
			collections = frappe.db.count("Collection")

			frappe.get_doc("Online Donation", gift.name).on_payment_authorized("Completed")

		self.assertEqual(self.status(gift), "Refunded")
		self.assertEqual(frappe.db.count("Collection"), collections)
		self.assertFalse(frappe.db.exists("Financial Transaction", {"parent": self.fund.name}))
		self.assertEqual(frappe.db.get_value("Fund", self.fund.name, "balance"), 0)

	def amend(self, collection):
		amended = frappe.copy_doc(collection)
		amended.update({"amended_from": collection.name, "docstatus": 0})
		return amended.insert(ignore_permissions=True)

	def test_a_gifts_collection_cannot_be_amended(self):
		"""The cancel marked the gift Refunded, so the amended copy would put its money back with no gift."""
		collection = self.make_collection("2031-03-01", 40)
		gift = self.gift(collection)
		collection.cancel()

		with self.assertRaises(frappe.ValidationError):
			self.amend(collection)
		self.assertFalse(frappe.db.exists("Collection", {"amended_from": collection.name}))
		self.assertEqual(self.status(gift), "Refunded")

		other = self.make_collection("2031-03-02", 15)
		other.cancel()
		self.assertTrue(self.amend(other).name)

	def test_cancelling_a_collection_with_no_gift_changes_no_gift(self):
		gift = self.gift(self.make_collection("2031-03-01", 40))
		self.make_collection("2031-03-02", 15).cancel()
		self.assertEqual(self.status(gift), "Paid")

	def test_a_negative_row_next_year_lowers_only_next_years_statement(self):
		self.make_collection("2031-03-01", 100)
		self.make_collection("2032-02-01", 50)
		self.make_collection("2032-04-01", -20)

		totals = [
			frappe.get_doc(
				{"doctype": "Giving Statement", "person": self.giver.name, "from_date": start, "to_date": end}
			)
			.insert(ignore_permissions=True)
			.total_amount
			for start, end in (("2031-01-01", "2031-12-31"), ("2032-01-01", "2032-12-31"))
		]
		self.assertEqual(totals, [100, 30])
