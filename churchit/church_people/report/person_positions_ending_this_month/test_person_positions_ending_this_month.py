# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.utils import add_days, today

from churchit.church_people.report.person_positions_ending_this_month.person_positions_ending_this_month import (
	execute,
)
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestPositionsEnding(RollbackEachTest):
	def make_term(self, name, end_date):
		ensure("Position Type", {"position": "_Test Term Position"}, {"position": "_Test Term Position"})
		person = make_person("_Test Term", name)
		person.append("positions", {"position": "_Test Term Position", "end_date": end_date})
		person.save(ignore_permissions=True)
		return person.name

	def people(self, filters=None):
		return [row["name"] for row in execute(filters)[1]]

	def test_a_term_ending_early_next_month_shows_by_default(self):
		soon = self.make_term("Soon", add_days(today(), 20))
		far = self.make_term("Far", add_days(today(), 90))
		past = self.make_term("Past", add_days(today(), -3))

		people = self.people()

		self.assertIn(soon, people)
		self.assertNotIn(far, people)
		self.assertNotIn(past, people)

	def test_the_dates_pick_the_window(self):
		far = self.make_term("Far", add_days(today(), 90))

		people = self.people({"from_date": add_days(today(), 80), "to_date": add_days(today(), 100)})

		self.assertIn(far, people)
