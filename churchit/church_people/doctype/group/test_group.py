# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.handler import execute_cmd
from frappe.utils import add_days, today

from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	GROUP_MESSAGES,
)
from churchit.church_people.doctype.group.group import add_people
from churchit.church_people.group_leaders import get_led_groups, is_group_leader, require_leader
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person


class TestGroup(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.member = make_person("_Test Group", "Member")
		cls.member.append("emails", {"email_address": "_test_group_member@example.com"})
		cls.member.save(ignore_permissions=True)
		cls.outsider = make_person("_Test Group", "Outsider")
		cls.user = ensure_user("_test_group_member@example.com", "_Test Group Member")
		frappe.db.set_value("Person", cls.member.name, "user", cls.user)

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

	def test_add_people_adds_new_members_and_skips_existing_ones(self):
		group = self._make_group("_Test Add People", members=[self.member.name])

		result = add_people(group.name, [self.member.name, self.outsider.name, self.outsider.name])

		self.assertEqual(result, {"added": 1, "already_members": 1})
		group.reload()
		self.assertEqual(
			sorted(row.person for row in group.members), sorted([self.member.name, self.outsider.name])
		)

	def test_add_people_refuses_a_get_request(self):
		"""Frappe checks the CSRF token only on POST, and the session cookie rides on a GET another site starts."""
		group = self._make_group("_Test Get Group")
		frappe.local.request = frappe._dict(method="GET")
		frappe.local.form_dict = frappe._dict(group=group.name, people=frappe.as_json([self.outsider.name]))
		try:
			with self.assertRaises(frappe.PermissionError):
				execute_cmd("churchit.church_people.doctype.group.group.add_people")
		finally:
			del frappe.local.request
			frappe.local.form_dict = frappe._dict()

		self.assertEqual(frappe.get_doc("Group", group.name).members, [])

	def test_add_people_needs_the_right_to_edit_the_group(self):
		group = self._make_group("_Test Locked Group")
		frappe.set_user(
			ensure_user("_test_group_staff@example.com", "_Test Group Staff", roles=("Church Staff",))
		)
		with self.assertRaises(frappe.PermissionError):
			add_people(group.name, [self.outsider.name])


class TestGroupLeaders(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_value("Group Role", "Leader", "is_leader", 1)
		cls.leader = make_person("_Test Leaders", "Leader")
		cls.member = make_person("_Test Leaders", "Member")
		cls.leader_user = ensure_user("_test_group_leader@example.com", "_Test Group Leader")
		cls.member_user = ensure_user("_test_group_led@example.com", "_Test Group Led")
		frappe.db.set_value("Person", cls.leader.name, "user", cls.leader_user)
		frappe.db.set_value("Person", cls.member.name, "user", cls.member_user)

	def setUp(self):
		super().setUp()
		self.group = frappe.get_doc({"doctype": "Group", "group_name": "_Test Led Group"})
		self.group.append("members", {"person": self.leader.name, "group_role": "Leader"})
		self.group.append("members", {"person": self.member.name, "group_role": "Member"})
		self.group.insert(ignore_permissions=True)

	def test_a_leader_row_leads_and_a_member_row_does_not(self):
		self.assertTrue(is_group_leader(self.group.name, self.leader.name))
		self.assertFalse(is_group_leader(self.group.name, self.member.name))
		self.assertEqual(get_led_groups(self.leader.name), [self.group.name])
		self.assertEqual(get_led_groups(self.member.name), [])

	def test_require_leader_returns_the_leader(self):
		frappe.set_user(self.leader_user)
		self.assertEqual(require_leader(self.group.name), self.leader.name)

	def test_require_leader_refuses_a_guest_a_member_and_a_user_with_no_person(self):
		for user in ("Guest", self.member_user, "Administrator"):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				require_leader(self.group.name)

	def test_the_starter_leader_role_leads_and_group_messages_cannot_be_deleted(self):
		self.assertEqual(frappe.db.get_value("Group Role", "Leader", "is_leader"), 1)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc("Communication Purpose", GROUP_MESSAGES)


class TestGroupEnrollment(RollbackEachTest):
	def make_group(self, members=0, **values):
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Enrollment",
				"status": "Active",
				"public": 1,
				"show_in_portal": 1,
				**values,
			}
		)
		for index in range(members):
			group.append("members", {"person": make_person("_Test Enrollment", str(index)).name})
		return group.insert(ignore_permissions=True)

	def test_a_full_group_is_closed(self):
		group = self.make_group(members=2, capacity=2)
		self.assertEqual(group.member_count, 2)
		self.assertTrue(group.is_full)
		self.assertFalse(group.is_enrollment_open)

	def test_no_capacity_is_never_full(self):
		group = self.make_group(members=2, capacity=0)
		self.assertFalse(group.is_full)
		self.assertTrue(group.is_enrollment_open)

	def test_enrollment_closes_after_its_date(self):
		self.assertTrue(self.make_group(close_enrollment_on=today()).is_enrollment_open)
		self.assertFalse(self.make_group(close_enrollment_on=add_days(today(), -1)).is_enrollment_open)

	def test_a_private_hidden_or_inactive_group_is_closed(self):
		for values in ({"public": 0}, {"show_in_portal": 0}, {"status": "Inactive"}):
			self.assertFalse(self.make_group(**values).is_enrollment_open, values)
