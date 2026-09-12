# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.doctype.group.group import create_email_group
from churchit.tests.helpers import ensure_user, make_person


class TestGroup(FrappeTestCase):
	def setUp(self):
		self.member = make_person("_Test Group", "Member")
		self.member.append("emails", {"email_address": "_test_group_member@example.com"})
		self.member.save(ignore_permissions=True)
		self.outsider = make_person("_Test Group", "Outsider")
		self.user = ensure_user("_test_group_member@example.com", "_Test Group Member")
		frappe.db.set_value("Person", self.member.name, "user", self.user)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _make_group(self, name, members=(), **values):
		group = frappe.get_doc({"doctype": "Group", "group_name": name, **values})
		for person in members:
			group.append("members", {"person": person})
		return group.insert(ignore_permissions=True)

	def test_portal_access_requires_portal_flag_and_membership(self):
		hidden = self._make_group("_Test Hidden", members=[self.member.name], show_in_portal=0)
		visible = self._make_group("_Test Visible", members=[self.member.name], show_in_portal=1)

		self.assertFalse(visible.has_webform_permission())  # Administrator has no Person
		frappe.set_user(self.user)
		self.assertTrue(visible.has_webform_permission())
		self.assertFalse(hidden.has_webform_permission())

	def test_guests_never_get_portal_access(self):
		group = self._make_group("_Test Guest Group", members=[self.member.name], show_in_portal=1)
		frappe.set_user("Guest")
		self.assertFalse(group.has_webform_permission())

	def test_create_email_group_collects_primary_emails_and_reports_missing(self):
		group = self._make_group("_Test Mailing List", members=[self.member.name, self.outsider.name])

		result = create_email_group(group.name)

		self.assertTrue(result["created"])
		self.assertEqual(result["email_group"], "_Test Mailing List")
		self.assertEqual(result["emails_synced"], 1)
		self.assertEqual(result["missing"], ["_Test Group Outsider"])
		self.assertEqual(result["total_members"], 1)
		self.assertTrue(
			frappe.db.exists(
				"Email Group Member",
				{"email_group": "_Test Mailing List", "email": "_test_group_member@example.com"},
			)
		)

	def test_create_email_group_is_idempotent(self):
		group = self._make_group("_Test Repeat List", members=[self.member.name])
		create_email_group(group.name)
		result = create_email_group(group.name)
		self.assertFalse(result["created"])
		self.assertEqual(result["total_members"], 1)
