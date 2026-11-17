# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.church_finances.report.person_donations import person_donations
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestPersonDonations(RollbackEachTest):
	def test_a_date_range_runs_to_the_end_of_the_last_day(self):
		giver = make_person("_Test Person Donations", "Giver").name
		row = {
			"person": giver,
			"fund": ensure("Fund", {"fund": "_Test Person Donations Fund"}),
			"payment_type": ensure("Payment Type", {"type": "Cash"}),
			"amount": 10,
		}
		give("2032-01-31 23:59:00", [row])
		inside = give("2032-02-01 00:00:00", [row])
		last = give("2032-02-29 23:59:00", [row])
		give("2032-03-01 00:00:00", [row])

		_columns, rows = person_donations.execute(
			{"person": giver, "from_date": "2032-02-01", "to_date": "2032-02-29"}
		)

		self.assertEqual([row["collection"] for row in rows], [last.name, inside.name])
