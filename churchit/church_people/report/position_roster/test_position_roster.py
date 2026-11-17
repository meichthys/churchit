# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

from frappe.utils import add_days, getdate

from churchit.church_people.report.position_roster import position_roster
from churchit.tests.helpers import RollbackEachTest, ensure, make_person

REPORT_DATE = "churchit.church_people.report.position_roster.position_roster.getdate"


class TestPositionRoster(RollbackEachTest):
	def test_a_current_term_is_the_one_that_holds_the_sites_date(self):
		position = ensure("Position Type", {"position": "_Test Roster Position"})
		term = {
			"position": position,
			"start_date": add_days(getdate(), 10),
			"end_date": add_days(getdate(), 40),
		}
		person = make_person("_Test Roster", "Term", positions=[term]).name

		def listed():
			return {row.person for row in position_roster.execute({"only_active": 1})[1]}

		self.assertNotIn(person, listed())
		with patch(REPORT_DATE, return_value=add_days(getdate(), 20)):
			self.assertIn(person, listed())
