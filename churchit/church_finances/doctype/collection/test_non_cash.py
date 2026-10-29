# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.giving_statement.test_giving_statement import make_collection
from churchit.church_finances.doctype.payment_type.payment_type import (
	NON_CASH,
	create_non_cash_payment_type,
)
from churchit.patches.v1_0 import add_non_cash_payment_type
from churchit.tests.helpers import RollbackEachTest, ensure, make_person

FUND = "_Test Non-Cash Fund"


class TestNonCashGifts(FrappeTestCase):
	"""A non-cash gift is described, never valued, so the ledger and totals stay cash only."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_non_cash_payment_type()
		cls.fund = ensure("Fund", {"fund": FUND})
		cls.giver = make_person("_Test NonCash", "Donor").name

	def gift(self, **values):
		return {
			"person": self.giver,
			"payment_type": NON_CASH,
			"amount": 0,
			"description": "_Test chairs",
			**values,
		}

	def test_a_non_cash_gift_needs_a_description(self):
		with self.assertRaises(frappe.ValidationError):
			make_collection("2029-02-01", [], fund=self.fund, rows=[self.gift(description=" ")])

	def test_a_non_cash_gift_states_no_amount(self):
		with self.assertRaises(frappe.ValidationError):
			make_collection("2029-02-01", [], fund=self.fund, rows=[self.gift(amount=50)])

	def test_a_submitted_non_cash_gift_adds_nothing_to_the_ledger_or_the_total(self):
		collection = make_collection("2029-02-01", [(self.giver, 10)], fund=self.fund, rows=[self.gift()])

		self.assertEqual(collection.total_amount, 10)
		self.assertEqual(
			frappe.get_all(
				"Financial Transaction",
				filters={"source_type": "Collection", "source": collection.name},
				pluck="amount",
			),
			[10],
		)
		self.assertEqual([row.is_non_cash for row in collection.donations], [0, 1])


class TestNonCashPaymentTypePatch(RollbackEachTest):
	def test_the_patch_adds_the_type_once(self):
		frappe.db.delete("Payment Type", {"is_non_cash": 1})
		frappe.db.delete("Payment Type", NON_CASH)

		add_non_cash_payment_type.execute()
		add_non_cash_payment_type.execute()

		self.assertEqual(frappe.get_all("Payment Type", filters={"is_non_cash": 1}, pluck="name"), [NON_CASH])

	def test_a_site_with_its_own_non_cash_type_gets_none(self):
		frappe.db.delete("Payment Type", {"is_non_cash": 1})
		frappe.db.delete("Payment Type", NON_CASH)
		frappe.get_doc({"doctype": "Payment Type", "type": "_Test In Kind", "is_non_cash": 1}).insert(
			ignore_permissions=True
		)

		add_non_cash_payment_type.execute()

		self.assertFalse(frappe.db.exists("Payment Type", NON_CASH))
