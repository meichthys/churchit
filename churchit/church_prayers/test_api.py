# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.handler import execute_cmd
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

	def make_request(self, visibility):
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": f"_Test {visibility} Request",
				"type": self.request.type,
				"visibility": visibility,
			}
		).insert(ignore_permissions=True)  # owned by Administrator

	def test_private_requests_are_only_prayable_by_their_owner(self):
		private = self.make_request("Private")

		frappe.set_user(self.user)
		with self.assertRaises(PermissionError):
			create_prayer(private.name)

	def test_prayer_team_requests_are_prayable_by_the_prayer_team_only(self):
		team_request = self.make_request("Prayer Team")

		team_member = ensure_user(
			"_test_prayer_team_user@example.com", "_Test Team", roles=("Church User", "Church Prayer Team")
		)
		make_person("_Test Praying", "Team", user=team_member)

		frappe.set_user(self.user)
		with self.assertRaises(PermissionError):
			create_prayer(team_request.name)

		frappe.set_user(team_member)
		self.assertTrue(create_prayer(team_request.name)["name"])

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

	def test_a_member_without_desk_read_gets_no_permission_message(self):
		"""The web form check lets the member pray, so the denied desk check must not leave a message."""
		frappe.set_user(self.user)
		self.assertFalse(frappe.get_doc("Prayer Request", self.request.name).has_permission("read"))

		frappe.local.message_log = []
		self.assertTrue(create_prayer(self.request.name)["name"])
		self.assertEqual(frappe.local.message_log, [])

	def test_praying_takes_a_post(self):
		"""Frappe checks the CSRF token only on a POST, and a GET from another site carries the session."""
		frappe.set_user(self.user)
		with (
			patch.object(frappe.local, "request", frappe._dict(method="GET"), create=True),
			patch.object(frappe.local, "form_dict", frappe._dict(prayer_request=self.request.name)),
			self.assertRaises(PermissionError),
		):
			execute_cmd("churchit.church_prayers.api.create_prayer")

		self.assertFalse(frappe.db.exists("Prayer", {"person": self.person}))
