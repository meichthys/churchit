# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.utils import add_days, getdate

from churchit.church_people.number_card.new_members_30_days import new_members_30_days
from churchit.church_people.report.new_members_last_90_days import new_members_last_90_days
from churchit.tests.helpers import RollbackEachTest, ensure, make_person


class TestNewMembers(RollbackEachTest):
	"""The New Members (30 days) card counts the rows the New Members report lists for 30 days."""

	def member(self, last_name, *dates, status="Active"):
		events = [{"event_type": "Membership", "date": date} for date in dates]
		return make_person(
			"_Test New Member", last_name, membership="Member", membership_status=status, life_events=events
		).name

	def test_the_card_and_the_report_count_first_membership_events_of_active_members(self):
		ensure("Life Event Type", {"type": "Membership"})
		ensure("Member Status", {"status": "Inactive"})
		today = getdate()
		card_before = new_members_30_days.get_count()["value"]

		joined = self.member("Joined", add_days(today, -10))
		left_out = {
			self.member("Inactive", add_days(today, -10), status="Inactive"),
			self.member("Rejoined", "2010-05-01", add_days(today, -5)),
			self.member("Future", add_days(today, 5)),
		}
		listed = {row.name for row in new_members_last_90_days.execute({"days": 30})[1]}

		self.assertIn(joined, listed)
		self.assertFalse(left_out & listed)
		self.assertEqual(new_members_30_days.get_count()["value"], card_before + 1)
