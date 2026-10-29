# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, force_single_church, make_two_churches


class TestRoom(FrappeTestCase):
	pass


def make_room(room_name, **values):
	return frappe.get_doc({"doctype": "Room", "room_name": room_name, **values}).insert(
		ignore_permissions=True
	)


class TestRoomNames(RollbackEachTest):
	"""A room is named by a counter, and its room name is unique among the rooms one church sees."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_new_room_is_named_by_a_counter(self):
		room = make_room("_Test Named Room", church=self.branch_a)
		self.assertTrue(room.name.startswith("ROOM-"), room.name)
		self.assertEqual(room.room_name, "_Test Named Room")

	def test_two_churches_can_each_have_a_sanctuary(self):
		in_a = make_room("_Test Sanctuary", church=self.branch_a)
		in_b = make_room("_Test Sanctuary", church=self.branch_b)
		self.assertNotEqual(in_a.name, in_b.name)

	def test_one_church_cannot_have_two_rooms_of_one_name(self):
		make_room("_Test Sanctuary", church=self.branch_a)
		with self.assertRaisesRegex(frappe.ValidationError, "already a room"):
			make_room("_Test Sanctuary", church=self.branch_a)

		other = make_room("_Test Chapel", church=self.branch_a)
		other.room_name = "_Test Sanctuary"
		with self.assertRaisesRegex(frappe.ValidationError, "already a room"):
			other.save(ignore_permissions=True)

	def test_a_shared_room_name_is_compared_with_every_church(self):
		"""Every church lists a shared room, so it may not share a name with any church's room."""
		make_room("_Test Sanctuary", church=self.branch_a)
		with self.assertRaisesRegex(frappe.ValidationError, "already a room"):
			make_room("_Test Sanctuary", church=self.branch_b, is_shared=1)

		make_room("_Test Hall", church=self.branch_a, is_shared=1)
		with self.assertRaisesRegex(frappe.ValidationError, "already a room"):
			make_room("_Test Hall", church=self.branch_b)

	def test_a_shared_room_keeps_its_name_when_saved_again(self):
		room = make_room("_Test Shared Room", church=self.branch_a, is_shared=1)
		room.capacity = 40
		room.save(ignore_permissions=True)

	def test_room_names_are_unique_in_single_church_mode(self):
		force_single_church()
		make_room("_Test Single Sanctuary")
		with self.assertRaisesRegex(frappe.ValidationError, "already a room"):
			make_room("_Test Single Sanctuary")


class TestRoomApprovers(RollbackEachTest):
	"""A room's listed approvers decide its bookings, or its church's Church Managers when none are listed."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		users = {
			"staff_a": ("Church Staff", cls.branch_a),
			"other_staff_a": ("Church Staff", cls.branch_a),
			"manager_a": ("Church Manager", cls.branch_a),
			"manager_b": ("Church Manager", cls.branch_b),
			"member_a": ("Church User", cls.branch_a),
		}
		for key, (role, church) in users.items():
			user = ensure_user(f"_test_room_{key}@example.com", key, roles=(role,))
			set_user_church(user, church)
			setattr(cls, key, user)

	def gated_room(self, approvers=(), **values):
		return make_room(
			"_Test Approval Room",
			church=self.branch_a,
			requires_approval=1,
			approvers=[{"user": user} for user in approvers],
			**values,
		)

	def test_only_the_listed_users_approve_a_room_with_a_list(self):
		room = self.gated_room([self.staff_a])
		self.assertEqual(room.get_approvers(), [self.staff_a])
		self.assertTrue(room.is_approver(self.staff_a))
		self.assertFalse(room.is_approver(self.other_staff_a))
		self.assertFalse(room.is_approver(self.manager_a))

	def test_the_church_managers_of_the_room_approve_a_room_without_a_list(self):
		room = self.gated_room()
		self.assertIn(self.manager_a, room.get_approvers())
		self.assertNotIn(self.manager_b, room.get_approvers())
		self.assertTrue(room.is_approver(self.manager_a))
		self.assertFalse(room.is_approver(self.manager_b))
		self.assertFalse(room.is_approver(self.staff_a))

	def test_a_shared_room_is_approved_by_the_church_that_shares_it(self):
		room = self.gated_room(is_shared=1)
		self.assertTrue(room.is_approver(self.manager_a))
		self.assertFalse(room.is_approver(self.manager_b))

	def test_an_approver_needs_a_staff_role_and_the_church_of_the_room(self):
		for user in (self.member_a, self.manager_b):
			with self.assertRaisesRegex(frappe.ValidationError, "cannot approve"):
				self.gated_room([user])

	def test_a_listed_user_who_loses_the_staff_role_no_longer_approves(self):
		demoted = ensure_user("_test_room_demoted@example.com", "demoted", roles=("Church Staff",))
		set_user_church(demoted, self.branch_a)
		frappe.get_doc("User", demoted).add_roles("Church Staff")
		room = self.gated_room([demoted, self.staff_a])
		frappe.get_doc("User", demoted).remove_roles("Church Staff")
		self.addCleanup(frappe.clear_cache, user=demoted)

		self.assertFalse(room.is_approver(demoted))
		self.assertEqual(room.get_approvers(), [self.staff_a])

	def test_every_church_manager_approves_in_single_church_mode(self):
		force_single_church()
		room = self.gated_room()
		self.assertTrue(room.is_approver(self.manager_b))
		self.assertIn(self.manager_b, room.get_approvers())
