# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.doctype.payment_type.payment_type import create_non_cash_payment_type
from churchit.church_finances.report.donations_by_person import donations_by_person
from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestDonationsByPerson(RollbackEachTest):
	def test_a_giver_of_property_only_is_not_listed(self):
		create_non_cash_payment_type()
		fund = ensure("Fund", {"fund": "_Test Donations By Person Fund"})
		giver = make_person("_Test Donations By Person", "Cash").name
		property_giver = make_person("_Test Donations By Person", "Property").name
		give(
			"2032-07-04 10:00:00",
			[
				{
					"person": giver,
					"fund": fund,
					"payment_type": ensure("Payment Type", {"type": "Cash"}),
					"amount": 25,
				},
				{
					"person": property_giver,
					"fund": fund,
					"payment_type": frappe.db.get_value("Payment Type", {"is_non_cash": 1}),
					"amount": 0,
					"description": "_Test piano",
				},
			],
		)

		_columns, rows = donations_by_person.execute({"from_date": "2032-07-01", "to_date": "2032-07-31"})

		self.assertEqual([row["person"] for row in rows[:-1]], [giver])
