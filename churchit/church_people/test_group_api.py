# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.handler import execute_cmd

from churchit.church_people.group_api import (
	get_member_groups,
	join_group,
	joinable_public_groups,
	leave_group,
)
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person


class TestGroupApi(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Group Role", {"role": "Member"})
		cls.user = ensure_user("_test_joiner@example.com", "_Test Joiner")
		cls.person = make_person("_Test Group", "Joiner", user=cls.user).name
		cls.stayer = make_person("_Test Group", "Stays").name
		cls.second_leader = make_person("_Test Group", "Second Leader").name
		cls.open_group = cls._group("_Test Open Group", public=1, show_in_portal=1)
		cls.hidden_group = cls._group("_Test Hidden Group", public=1, show_in_portal=0)
		cls.closed_group = cls._group("_Test Closed Group", public=0, show_in_portal=1)

	def setUp(self):
		super().setUp()
		frappe.set_user(self.user)

	@staticmethod
	def _group(name, **values):
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

	def test_member_groups_are_the_callers_own_groups(self):
		self.assertEqual(get_member_groups(), [])

		join_group(self.open_group.name)
		self.assertEqual(get_member_groups(), [self.open_group.name])

		frappe.set_user(ensure_user("_test_other_joiner@example.com", "_Test Other Joiner"))
		self.assertEqual(get_member_groups(), [], "a user with no Person is in no group")

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

	def test_a_get_request_joins_nothing(self):
		"""Frappe checks the CSRF token only on POST, and the session cookie rides on a GET another site starts."""
		frappe.local.request = frappe._dict(method="GET")
		frappe.local.form_dict = frappe._dict(group=self.open_group.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				execute_cmd("churchit.church_people.group_api.join_group")
		finally:
			del frappe.local.request
			frappe.local.form_dict = frappe._dict()

		self.assertFalse(frappe.db.exists("Group Member", {"parent": self.open_group.name}))

	def test_join_requires_a_linked_person(self):
		frappe.set_user(ensure_user("_test_unlinked_joiner@example.com", "_Test Unlinked"))
		with self.assertRaises(ValidationError):
			join_group(self.open_group.name)

	def test_leaving_removes_only_the_callers_own_row(self):
		other = self.stayer
		group = self._group("_Test Leave Group", public=1, show_in_portal=1)
		group.append("members", {"person": other})
		group.save(ignore_permissions=True)
		join_group(group.name)

		self.assertEqual(leave_group(group.name), {"left": True, "group_name": "_Test Leave Group"})

		members = frappe.get_all("Group Member", filters={"parent": group.name}, pluck="person")
		self.assertEqual(members, [other])

	def test_leaving_a_group_you_are_not_in_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			leave_group(self.open_group.name)

	def test_the_only_leader_cannot_leave(self):
		role = ensure(
			"Group Role", {"role": "_Test Leave Leader"}, {"role": "_Test Leave Leader", "is_leader": 1}
		)
		group = self._group("_Test Led Leave Group")
		group.append("members", {"person": self.person, "group_role": role})
		group.save(ignore_permissions=True)

		with self.assertRaises(ValidationError):
			leave_group(group.name)
		self.assertTrue(frappe.db.exists("Group Member", {"parent": group.name, "person": self.person}))

		second = self.second_leader
		group.append("members", {"person": second, "group_role": role})
		group.save(ignore_permissions=True)
		leave_group(group.name)
		self.assertFalse(frappe.db.exists("Group Member", {"parent": group.name, "person": self.person}))

	def test_leaving_takes_a_post_and_a_linked_person(self):
		frappe.local.request = frappe._dict(method="GET")
		frappe.local.form_dict = frappe._dict(group=self.open_group.name)
		try:
			with self.assertRaises(frappe.PermissionError):
				execute_cmd("churchit.church_people.group_api.leave_group")
		finally:
			del frappe.local.request
			frappe.local.form_dict = frappe._dict()

		frappe.set_user(ensure_user("_test_unlinked_leaver@example.com", "_Test Unlinked Leaver"))
		with self.assertRaises(frappe.PermissionError):
			leave_group(self.open_group.name)
