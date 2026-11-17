# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate, today

from churchit.church_finances.report.first_time_givers import first_time_givers
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


def give(date, rows, **values):
	"""Submit a Collection on *date* of *rows* (person, fund, payment type, amount and check number)."""
	collection = frappe.get_doc(
		{
			"doctype": "Collection",
			"date": date,
			"expected_total": sum(row["amount"] for row in rows),
			"donations": rows,
			**values,
		}
	).insert(ignore_permissions=True)
	return collection.submit()


class TestFirstTimeGivers(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.general = ensure("Fund", {"fund": "_Test First Gift General"})
		cls.building = ensure("Fund", {"fund": "_Test First Gift Building"})
		cls.cash = ensure("Payment Type", {"type": "Cash"})
		cls.check = ensure("Payment Type", {"type": "Check"})

	def row(self, person, fund, payment_type, amount, check_number=None):
		return {
			"person": person,
			"fund": fund,
			"payment_type": payment_type,
			"amount": amount,
			"check_number": check_number,
		}

	def test_the_first_gift_is_everything_given_on_the_first_day(self):
		giver = make_person("_Test First Gift", "Split").name
		first_day = add_days(getdate(today()), -3)
		give(
			f"{first_day} 09:00:00",
			[
				self.row(giver, self.general, self.check, 100, "1001"),
				self.row(giver, self.building, self.check, 500, "1001"),
			],
		)
		give(f"{first_day} 18:00:00", [self.row(giver, self.general, self.cash, 40)])
		give(f"{add_days(first_day, 1)} 09:00:00", [self.row(giver, self.general, self.cash, 50)])

		rows = {row.person: row for row in first_time_givers.execute({})[1]}

		self.assertEqual(getdate(rows[giver].first_gift_date), first_day)
		self.assertEqual(rows[giver].first_gift_amount, 640)

	def test_a_giver_before_the_window_is_no_first_time_giver(self):
		giver = make_person("_Test First Gift", "Long Ago").name
		give(f"{add_days(today(), -40)} 09:00:00", [self.row(giver, self.general, self.cash, 10)])
		give(f"{add_days(today(), -2)} 09:00:00", [self.row(giver, self.general, self.cash, 20)])

		people = [row.person for row in first_time_givers.execute({"window_days": 30})[1]]

		self.assertNotIn(giver, people)
		self.assertIn(giver, [row.person for row in first_time_givers.execute({"window_days": 41})[1]])
