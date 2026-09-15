# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.group_api import join_group, joinable_public_groups
from churchit.tests.helpers import ensure, ensure_user, make_person


class TestGroupApi(FrappeTestCase):
	def setUp(self):
		ensure("Group Role", {"role": "Member"})
		self.user = ensure_user("_test_joiner@example.com", "_Test Joiner")
		self.person = make_person("_Test Group", "Joiner", user=self.user).name
		self.open_group = self._group("_Test Open Group", public=1, show_in_portal=1)
		self.hidden_group = self._group("_Test Hidden Group", public=1, show_in_portal=0)
		self.closed_group = self._group("_Test Closed Group", public=0, show_in_portal=1)
		frappe.set_user(self.user)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _group(self, name, **values):
		return frappe.get_doc({"doctype": "Group", "group_name": name, **values}).insert(
			ignore_permissions=True
		)

	def test_joinable_groups_are_public_portal_groups_the_user_is_not_in(self):
		names = {row.name for row in joinable_public_groups()}
		self.assertIn(self.open_group.name, names)
		self.assertNotIn(self.hidden_group.name, names)
		self.assertNotIn(self.closed_group.name, names)

		join_group(self.open_group.name)
		self.assertNotIn(self.open_group.name, {row.name for row in joinable_public_groups()})

	def test_join_adds_the_person_with_the_member_role(self):
		self.assertEqual(join_group(self.open_group.name), {"joined": True, "group_name": "_Test Open Group"})
		members = frappe.get_all(
			"Group Member", filters={"parent": self.open_group.name}, fields=["person", "group_role"]
		)
		self.assertEqual([(m.person, m.group_role) for m in members], [(self.person, "Member")])

	def test_joining_twice_reports_existing_membership(self):
		join_group(self.open_group.name)
		self.assertEqual(
			join_group(self.open_group.name), {"already_member": True, "group_name": "_Test Open Group"}
		)

	def test_join_rejects_missing_hidden_and_private_groups(self):
		for group in ("", "GRP-DOES-NOT-EXIST", self.hidden_group.name, self.closed_group.name):
			with self.assertRaises(ValidationError):
				join_group(group)

	def test_join_requires_a_linked_person(self):
		frappe.set_user(ensure_user("_test_unlinked_joiner@example.com", "_Test Unlinked"))
		with self.assertRaises(ValidationError):
			join_group(self.open_group.name)
