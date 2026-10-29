# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.modules.patch_handler import PatchType, get_patches_from_app
from frappe.tests.utils import FrappeTestCase

from churchit.church_prayers.web_form.community_prayer_requests import community_prayer_requests
from churchit.patches.v1_0 import set_prayer_request_visibility
from churchit.tests.helpers import ensure, ensure_user


class TestPrayerAccess(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		cls.private, cls.team, cls.whole = (
			frappe.get_doc(
				{
					"doctype": "Prayer Request",
					"title": f"_Test Access {visibility}",
					"type": request_type,
					"visibility": visibility,
				}
			).insert(ignore_permissions=True)
			for visibility in ("Private", "Prayer Team", "Whole Church")
		)
		cls.member = ensure_user("_test_access_member@example.com", "_Test Member")
		cls.praying = ensure_user(
			"_test_access_team@example.com", "_Test Team", roles=("Church User", "Church Prayer Team")
		)
		cls.staff_praying = ensure_user(
			"_test_access_staff_team@example.com", "_Test Staff", roles=("Church Staff", "Church Prayer Team")
		)
		cls.care = ensure_user("_test_access_care@example.com", "_Test Care", roles=("Church Pastoral Care",))
		cls.own_private = frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Access Own Private",
				"type": request_type,
				"visibility": "Private",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Prayer Request", cls.own_private.name, "owner", cls.praying)

	def tearDown(self):
		frappe.set_user("Administrator")

	def readable(self, user):
		"""The test requests *user* lists, and the ones they may open."""
		names = {self.private.name, self.team.name, self.whole.name, self.own_private.name}
		frappe.set_user(user)
		listed = set(frappe.get_list("Prayer Request", filters={"name": ("in", names)}, pluck="name"))
		opened = {name for name in names if frappe.has_permission("Prayer Request", "read", doc=name)}
		frappe.set_user("Administrator")
		return listed, opened

	def test_the_prayer_team_reads_every_request_but_another_persons_private_one(self):
		expected = {self.team.name, self.whole.name, self.own_private.name}
		self.assertEqual(self.readable(self.praying), (expected, expected))

	def test_staff_on_the_prayer_team_still_cannot_read_private_requests(self):
		expected = {self.team.name, self.whole.name}
		self.assertEqual(self.readable(self.staff_praying), (expected, expected))

	def test_a_member_reads_only_their_own_requests(self):
		self.assertEqual(self.readable(self.member), (set(), set()))

	def test_pastoral_care_reads_private_requests(self):
		listed, opened = self.readable(self.care)
		self.assertIn(self.private.name, listed)
		self.assertIn(self.private.name, opened)

	def test_the_community_page_hides_closed_ended_and_unapproved_requests(self):
		ensure("Prayer Request Status", {"status": "Answered"})
		hidden = {
			frappe.get_doc(
				{
					"doctype": "Prayer Request",
					"title": f"_Test Access {title}",
					"type": self.whole.type,
					"visibility": "Whole Church",
					**values,
				}
			)
			.insert(ignore_permissions=True)
			.name
			for title, values in (
				("Answered", {"status": "Answered"}),
				("Ended", {"end_date": "2020-01-01 00:00:00"}),
				("Unapproved", {"approved_for_list": 0}),
			)
		}

		frappe.set_user(self.member)
		context = community_prayer_requests.get_list_context(frappe._dict())
		listed = {row.name for row in context.get_list("Prayer Request", "", [], 0, 500)}

		self.assertIn(self.whole.name, listed)
		self.assertFalse(hidden & listed)
		self.assertTrue(frappe.get_doc("Prayer Request", self.whole.name).has_webform_permission())
		for name in hidden:
			self.assertFalse(frappe.get_doc("Prayer Request", name).has_webform_permission(), name)


class TestVisibilityPatch(FrappeTestCase):
	def ticked_and_plain(self):
		if not frappe.db.has_column("Prayer Request", "is_private"):
			self.skipTest("This site never had Is Private")
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		ticked, plain = (
			frappe.get_doc(
				{"doctype": "Prayer Request", "title": f"_Test Patch {title}", "type": request_type}
			).insert(ignore_permissions=True)
			for title in ("Ticked", "Plain")
		)
		frappe.db.set_value("Prayer Request", ticked.name, "is_private", 1)
		return ticked, plain

	def test_the_ticks_move_before_model_sync(self):
		"""Model sync gives every request the default, Whole Church, so a later patch would leave a gap."""
		self.assertIn(
			set_prayer_request_visibility.__name__, get_patches_from_app("churchit", PatchType.pre_model_sync)
		)

	def test_before_model_sync_the_patch_adds_visibility_itself(self):
		ticked, _plain = self.ticked_and_plain()
		has_column = frappe.db.has_column

		with (
			patch.object(
				frappe.local.db,
				"has_column",
				side_effect=lambda doctype, column: column != "visibility" and has_column(doctype, column),
			),
			patch("frappe.reload_doc") as reload_doc,
		):
			set_prayer_request_visibility.execute()

		reload_doc.assert_called_once_with("church_prayers", "doctype", "prayer_request", force=True)
		self.assertEqual(frappe.db.get_value("Prayer Request", ticked.name, "visibility"), "Private")

	def test_a_ticked_request_becomes_private_once(self):
		ticked, plain = self.ticked_and_plain()

		set_prayer_request_visibility.execute()
		self.assertEqual(frappe.db.get_value("Prayer Request", ticked.name, "visibility"), "Private")
		self.assertEqual(frappe.db.get_value("Prayer Request", plain.name, "visibility"), "Whole Church")

		frappe.db.set_value("Prayer Request", ticked.name, "visibility", "Prayer Team")
		set_prayer_request_visibility.execute()
		self.assertEqual(frappe.db.get_value("Prayer Request", ticked.name, "visibility"), "Prayer Team")
