# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure, ensure_user, make_person


class TestPrayerRequest(FrappeTestCase):
	def setUp(self):
		self.request_type = ensure("Prayer Request Type", {"type": "Health"})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _request(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Request",
				"type": self.request_type,
				**values,
			}
		).insert(ignore_permissions=True)

	def test_status_defaults_to_requested(self):
		request = self._request(status=None)
		self.assertEqual(request.status, "Requested")

	def test_recipient_name_resolves_the_linked_title(self):
		person = make_person("_Test Prayer", "Recipient")
		request = self._request(recipient_type="Person", recipient=person.name)
		self.assertEqual(request.recipient_name, "_Test Prayer Recipient")

	def test_recipient_name_cleared_without_recipient(self):
		request = self._request(recipient_name="stale")
		self.assertIsNone(request.recipient_name)

	def test_webform_permission_allows_public_requests_to_logged_in_users(self):
		public = self._request(is_private=0)
		private = self._request(is_private=1)

		frappe.set_user(ensure_user("_test_prayer_reader@example.com", "_Test Reader"))
		self.assertTrue(public.has_webform_permission())
		self.assertFalse(private.has_webform_permission())

		frappe.set_user("Guest")
		self.assertFalse(public.has_webform_permission())
