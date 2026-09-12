# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_prayers.api import create_prayer
from churchit.tests.helpers import ensure, ensure_user, make_person


class TestPrayerApi(FrappeTestCase):
	def setUp(self):
		self.user = ensure_user("_test_prayer_user@example.com", "_Test Prayer User")
		self.person = make_person("_Test Praying", "Member", user=self.user).name
		self.request = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Public Request",
				"type": ensure("Prayer Request Type", {"type": "Health"}),
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guests_cannot_pray(self):
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			create_prayer(self.request.name)

	def test_private_requests_are_only_prayable_by_their_owner(self):
		private = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Private Request",
				"type": self.request.type,
				"is_private": 1,
			}
		).insert(ignore_permissions=True)  # owned by Administrator

		frappe.set_user(self.user)
		with self.assertRaises(PermissionError):
			create_prayer(private.name)

	def test_user_without_a_person_record_is_rejected(self):
		frappe.set_user(ensure_user("_test_prayer_orphan@example.com", "_Test Orphan"))
		with self.assertRaises(ValidationError):
			create_prayer(self.request.name)

	def test_prayer_is_recorded_against_the_request(self):
		frappe.set_user(self.user)
		result = create_prayer(self.request.name, content="Lord, hear us")

		prayer = frappe.get_doc("Prayer", result["name"])
		self.assertEqual(prayer.person, self.person)
		self.assertEqual(prayer.content, "Lord, hear us")
		self.assertEqual(
			[(row.topic_type, row.topic) for row in prayer.topics],
			[("Prayer Request", self.request.name)],
		)
