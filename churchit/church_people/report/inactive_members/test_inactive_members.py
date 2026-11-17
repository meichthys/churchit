# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

from frappe.utils import add_days, getdate

from churchit.church_people.report.inactive_members import inactive_members
from churchit.tests.helpers import RollbackEachTest, make_function, make_person

REPORT_DATE = "churchit.church_people.report.inactive_members.inactive_members.getdate"


class TestInactiveMembers(RollbackEachTest):
	def member(self, last_name):
		return make_person("_Test Inactive", last_name, membership="Member", membership_status="Active").name

	def attend(self, person, start_date, attendance_type="Confirmed"):
		function = make_function("_Test Inactive Service", start_date=start_date)
		function.append("attendance", {"person": person, "attendance_type": attendance_type})
		function.save(ignore_permissions=True)

	def rows(self, **filters):
		return {row.name: row for row in inactive_members.execute(filters)[1]}

	def test_lists_members_absent_longer_than_the_threshold_by_their_last_counted_visit(self):
		today = getdate()
		absent, recent, never = self.member("Absent"), self.member("Recent"), self.member("Never")
		self.attend(absent, add_days(today, -100))
		self.attend(absent, add_days(today, -90))
		self.attend(absent, add_days(today, -5), attendance_type="Absent")
		self.attend(recent, add_days(today, -10))

		rows = self.rows(threshold_days=60)

		self.assertEqual((rows[absent].last_attended, rows[absent].days_absent), (add_days(today, -90), 90))
		self.assertNotIn(recent, rows)
		self.assertEqual((rows[never].last_attended, rows[never].days_absent), (None, None))

	def test_days_absent_count_from_the_sites_date(self):
		today = getdate()
		person = self.member("Site Date")
		self.attend(person, add_days(today, -10))

		with patch(REPORT_DATE, return_value=add_days(today, 61)):
			rows = self.rows(threshold_days=60)

		self.assertEqual(rows[person].days_absent, 71)
