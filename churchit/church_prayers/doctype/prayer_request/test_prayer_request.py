# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.client import insert, set_value
from frappe.desk.form.save import savedocs
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.web_form.web_form import accept

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

	def test_webform_permission_allows_whole_church_requests_to_logged_in_users(self):
		public = self._request(visibility="Whole Church")
		private = self._request(visibility="Private")

		frappe.set_user(ensure_user("_test_prayer_reader@example.com", "_Test Reader"))
		self.assertTrue(public.has_webform_permission())
		self.assertFalse(private.has_webform_permission())

		frappe.set_user("Guest")
		self.assertFalse(public.has_webform_permission())

	def test_visibility_defaults_to_whole_church(self):
		self.assertEqual(self._request().visibility, "Whole Church")

	def test_a_guest_request_waits_for_approval(self):
		ensure("Prayer Request Status", {"status": "Answered"})
		frappe.set_user("Guest")
		guest = accept(
			"prayer-request-anonymous",
			json.dumps(
				{
					"title": "_Test Guest Request",
					"type": self.request_type,
					"request": "Please pray.",
					"status": "Answered",
					"visibility": "Prayer Team",
				}
			),
		)
		self.assertEqual(guest.status, "Requested")
		self.assertEqual(guest.visibility, "Prayer Team")
		self.assertEqual(guest.approved_for_list, 0)

		member = ensure_user("_test_prayer_approved@example.com", "_Test Approved")
		if not frappe.db.exists("Person", {"user": member}):
			make_person("_Test Prayer", "Approved", user=member)
		frappe.set_user(member)
		request = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Member Request",
				"type": self.request_type,
				"approved_for_list": 0,
			}
		).insert()
		self.assertEqual(request.approved_for_list, 1)

	def test_a_member_cannot_set_the_status(self):
		ensure("Prayer Request Status", {"status": "Answered"})
		member = ensure_user("_test_prayer_status@example.com", "_Test Status")
		if not frappe.db.exists("Person", {"user": member}):
			make_person("_Test Prayer", "Status", user=member)
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)
		values = {
			"title": "_Test Status Request",
			"type": self.request_type,
			"request": "Please pray.",
			"visibility": "Private",
			"status": "Answered",
		}

		frappe.set_user(member)
		saved = accept("prayer-request", json.dumps(values))
		self.assertEqual(saved.status, "Requested")
		self.assertEqual(
			accept("prayer-request", json.dumps({**values, "name": saved.name})).status, "Requested"
		)
		frappe.flags.in_web_form = False
		self.assertEqual(insert({"doctype": "Prayer Request", **values})["status"], "Requested")

		frappe.set_user(
			ensure_user("_test_prayer_status_manager@example.com", "_Test", roles=("Church Manager",))
		)
		set_value("Prayer Request", saved.name, "status", "Answered")

		frappe.set_user(member)
		set_value("Prayer Request", saved.name, "status", "Requested")
		self.assertEqual(frappe.db.get_value("Prayer Request", saved.name, "status"), "Answered")
		self.assertEqual(
			frappe.get_list("Prayer Request", {"name": saved.name}, pluck="status"), ["Answered"]
		)

	def test_church_staff_cannot_approve_a_request_from_the_list_edit(self):
		"""The list's Edit action saves each document, so the permlevel 1 rule still holds there."""
		staff = ensure_user("_test_prayer_staff_edit@example.com", "_Test Staff", roles=("Church Staff",))
		own, other = (self._request(approved_for_list=0).name for _ in range(2))
		frappe.db.set_value("Prayer Request", own, "owner", staff)

		frappe.set_user(staff)
		request = frappe.get_doc("Prayer Request", own)
		request.update({"approved_for_list": 1})
		request.save()
		self.assertEqual(frappe.db.get_value("Prayer Request", own, "approved_for_list"), 0)

		request = frappe.get_doc("Prayer Request", other)
		request.update({"approved_for_list": 1})
		with self.assertRaises(frappe.PermissionError):
			request.save()

	def test_a_form_opened_before_a_prayer_keeps_the_new_count(self):
		"""recount_prayers leaves `modified` alone, so Frappe does not refuse the stale form."""
		request = self._request()
		opened = frappe.get_doc("Prayer Request", request.name).as_dict()
		frappe.get_doc(
			{
				"doctype": "Prayer",
				"person": make_person("_Test Stale", "Prayer").name,
				"date": "2031-05-01 09:30:00",
				"topics": [{"topic_type": "Prayer Request", "topic": request.name}],
			}
		).insert(ignore_permissions=True)

		savedocs(json.dumps(opened, default=str), "Save")

		self.assertEqual(frappe.db.get_value("Prayer Request", request.name, "prayer_count"), 1)
