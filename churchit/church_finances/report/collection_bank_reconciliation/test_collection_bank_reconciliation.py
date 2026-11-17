# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.doctype.payment_type.payment_type import create_non_cash_payment_type
from churchit.church_finances.report.collection_bank_reconciliation import collection_bank_reconciliation
from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestCollectionBankReconciliation(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_non_cash_payment_type()
		cls.non_cash = frappe.db.get_value("Payment Type", {"is_non_cash": 1})
		cls.fund = ensure("Fund", {"fund": "_Test Bank Fund"})
		cls.giver = make_person("_Test Bank", "Giver").name

	def make_collection(self):
		return give(
			"2032-02-01 10:00:00",
			[
				{
					"person": self.giver,
					"fund": self.fund,
					"payment_type": ensure("Payment Type", {"type": "Check"}),
					"check_number": "300",
					"amount": 50,
				},
				{
					"person": self.giver,
					"fund": self.fund,
					"payment_type": self.non_cash,
					"amount": 0,
					"description": "_Test laptop",
				},
			],
		)

	def test_donated_property_is_no_bank_line(self):
		collection = self.make_collection()

		result = collection_bank_reconciliation.execute({"parent_filter": collection.name})

		self.assertEqual([(row["check_number"], row["amount"]) for row in result[1]], [("300", 50)])
		self.assertEqual(len(result), 2)

	def test_a_cancelled_collection_says_so(self):
		collection = self.make_collection()
		collection.cancel()

		_columns, _rows, message = collection_bank_reconciliation.execute({"parent_filter": collection.name})

		self.assertIn("cancelled", message)
