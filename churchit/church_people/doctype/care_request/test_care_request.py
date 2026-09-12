# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, nowdate

from churchit.tests.helpers import ensure, ensure_user, make_person


class TestCareRequest(FrappeTestCase):
	def setUp(self):
		self.category = ensure("Care Request Type", {"type": "_Test Need"})
		self.person = make_person("_Test Care", "Requester").name
		self.deacon = make_person("_Test Care", "Deacon").name

	def tearDown(self):
		frappe.set_user("Administrator")

	def _assign(self, deacon, start_date, end_date=None):
		return frappe.get_doc(
			{
				"doctype": "Care Assignment",
				"person": self.person,
				"deacon": deacon,
				"start_date": start_date,
				"end_date": end_date,
			}
		).insert(ignore_permissions=True)

	def _request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": self.person,
				"category": self.category,
				"description": "Needs a hand",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_assigned_to_defaults_to_the_current_deacon(self):
		self._assign(self.deacon, add_days(nowdate(), -10))
		self.assertEqual(self._request().assigned_to, self.deacon)

	def test_ended_assignments_are_ignored(self):
		self._assign(self.deacon, add_days(nowdate(), -30), end_date=add_days(nowdate(), -1))
		self.assertIsNone(self._request().assigned_to)

	def test_assignment_ending_today_still_counts(self):
		self._assign(self.deacon, add_days(nowdate(), -30), end_date=nowdate())
		self.assertEqual(self._request().assigned_to, self.deacon)

	def test_explicit_assignee_is_kept(self):
		self._assign(self.deacon, add_days(nowdate(), -10))
		other = make_person("_Test Care", "Other Deacon").name
		self.assertEqual(self._request(assigned_to=other).assigned_to, other)

	def test_person_defaults_to_the_logged_in_users_person(self):
		user = ensure_user("_test_care_user@example.com", "_Test Care User")
		frappe.db.set_value("Person", self.person, "user", user)
		frappe.set_user(user)

		request = frappe.get_doc(
			{"doctype": "Care Request", "category": self.category, "description": "Portal ask"}
		).insert(ignore_permissions=True)
		self.assertEqual(request.person, self.person)
