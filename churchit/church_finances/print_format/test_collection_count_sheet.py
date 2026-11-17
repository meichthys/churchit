# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.doctype.payment_type.payment_type import create_non_cash_payment_type
from churchit.tests.helpers import RollbackEachTest, ensure, make_function, make_person


class TestCollectionCountSheet(RollbackEachTest):
	def make_collection(self, rows, **values):
		collection = frappe.get_doc(
			{
				"doctype": "Collection",
				"date": "2032-03-07 10:00:00",
				"expected_total": sum(row["amount"] for row in rows),
				"donations": rows,
				**values,
			}
		)
		return collection.insert(ignore_permissions=True)

	def test_the_header_names_the_function_without_its_date_again(self):
		function = make_function("_Test Count Worship", start_date="2032-03-07")
		cash = ensure("Payment Type", {"type": "Cash"})
		fund = ensure("Fund", {"fund": "_Test Count Fund"})
		collection = self.make_collection(
			[{"payment_type": cash, "fund": fund, "amount": 10}], function=function.name
		)

		html = frappe.get_print("Collection", collection.name, "Collection Count Sheet")

		self.assertIn("Function: _Test Count Worship\n", html)
		self.assertNotIn("_Test Count Worship: 2032-03-07", html)
		self.assertNotIn("Non-Cash Gifts Received", html)

	def test_non_cash_gifts_are_listed_under_the_fund_table(self):
		create_non_cash_payment_type()
		giver = make_person("_Test Count", "Giver")
		fund = ensure("Fund", {"fund": "_Test Count Building"})
		collection = self.make_collection(
			[
				{
					"payment_type": frappe.db.get_value("Payment Type", {"is_non_cash": 1}),
					"fund": fund,
					"person": giver.name,
					"amount": 0,
					"description": "_Test hymnals <b>x12</b>",
				}
			]
		)

		html = frappe.get_print("Collection", collection.name, "Collection Count Sheet")

		self.assertIn("Non-Cash Gifts Received", html)
		self.assertIn(f"<td>{giver.full_name}</td><td>_Test Count Building</td>", html)
		self.assertIn("_Test hymnals &lt;b&gt;x12&lt;/b&gt;", html)
