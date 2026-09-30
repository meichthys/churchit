# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The church boundary, tested from the side the desk does not guard.

The desk hides what a user may not reach: a link field's dropdown filters by
church, and its pre-save check refuses a name typed in by hand. None of that is
a rule, though, and every one of these went through a whitelisted call that any
Church Manager can make. A record another church shared is the mirror image: it
is readable and writable by everyone, so the only thing keeping it in the
organisation is a guard that says who may take it away.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from churchit.church_ministries.doctype.function.function import apply_template
from churchit.church_ministries.doctype.function_check_in.function_check_in import check_in_persons
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	get_function_item_totals,
	get_item_status,
)
from churchit.church_ministries.page.check_in.check_in import get_check_ins, search_people
from churchit.church_people.doctype.group.group import create_email_group
from churchit.church_people.group_api import join_group
from churchit.church_prayers.number_card.prayer_request_comments import prayer_request_comments
from churchit.church_scope import SHARED
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
	set_private_people,
)


class TestChurchBoundary(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch_a = make_branch("_Test Boundary A", "TDA")
		cls.branch_b = make_branch("_Test Boundary B", "TDB")
		cls.manager_a = cls.bind_manager("_test_boundary_a@example.com", "BoundaryA", cls.branch_a)
		cls.manager_b = cls.bind_manager("_test_boundary_b@example.com", "BoundaryB", cls.branch_b)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def bind_manager(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Manager",))
		make_person(first_name, "Manager", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def keep_people_private(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

	def shared_song(self, title):
		"""A song branch A shares with every church."""
		song = ensure("Song", {"title": title}, {"title": title, "church": self.branch_a})
		doc = frappe.get_doc("Song", song)
		doc.is_shared = 1
		doc.save(ignore_permissions=True)
		return doc

	def test_a_recipient_church_cannot_delete_what_was_shared_with_it(self):
		"""Unticking the box is refused for a recipient; deleting is the same loss."""
		song = self.shared_song("_Test Boundary Shared Song")

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Song", song.name)
		self.assertTrue(frappe.db.exists("Song", song.name))

	def test_the_church_that_shared_a_record_can_still_delete_it(self):
		song = self.shared_song("_Test Boundary Own Song")

		frappe.set_user(self.manager_a)
		frappe.delete_doc("Song", song.name)
		self.assertFalse(frappe.db.exists("Song", song.name))

	def test_a_user_holding_no_church_cannot_unshare_another_churchs_record(self):
		"""Holding no Church permission means unrestricted reading, not ownership."""
		song = self.shared_song("_Test Boundary Loose Song")
		user = ensure_user("_test_boundary_loose@example.com", "Loose", roles=("Church Manager",))
		for permission in frappe.get_all(
			"User Permission", filters={"user": user, "allow": "Church"}, pluck="name"
		):
			frappe.delete_doc("User Permission", permission, ignore_permissions=True, force=True)

		frappe.set_user(user)
		doc = frappe.get_doc("Song", song.name)
		doc.is_shared = 0
		with self.assertRaises(frappe.PermissionError):
			doc.save()

	def test_unsharing_a_room_takes_its_bookings_out_of_every_church(self):
		"""A booking of a shared room is shared with it, and has to come back with it."""
		room = frappe.get_doc(
			{
				"doctype": "Room",
				"room_name": "_Test Boundary Hall",
				"church": self.branch_a,
				"is_bookable": 1,
				"is_shared": 1,
			}
		).insert(ignore_permissions=True)
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room.name,
				"requester": make_person("_Test Boundary", "Booker", church=self.branch_a).name,
				"start_datetime": "2033-08-08 10:00:00",
				"end_datetime": "2033-08-08 11:00:00",
				"purpose": "_Test Boundary",
			}
		).insert(ignore_permissions=True)
		self.assertEqual(booking.church, SHARED)

		room.reload()
		room.is_shared = 0
		room.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Room Booking", booking.name, "church"), self.branch_a)
		frappe.set_user(self.manager_b)
		self.assertFalse(frappe.has_permission("Room Booking", "read", doc=booking.name))

	def transfer(self, person, to_church):
		return frappe.get_doc(
			{
				"doctype": "Member Transfer",
				"person": person,
				"direction": "Out",
				"to_church": to_church,
				"status": "Confirmed",
			}
		).insert()

	def test_a_transfer_cannot_reach_a_person_of_another_church(self):
		"""`person` is a plain Link, so nothing else looks at whose member it is."""
		theirs = make_person("_Test Boundary Theirs", "Person", church=self.branch_a)

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			self.transfer(theirs.name, self.branch_b)
		self.assertEqual(frappe.db.get_value("Person", theirs.name, "church"), self.branch_a)

	def test_a_transfer_cannot_send_a_person_to_a_church_you_do_not_hold(self):
		mine = make_person("_Test Boundary Mine", "Person", church=self.branch_b)

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			self.transfer(mine.name, self.branch_a)
		self.assertEqual(frappe.db.get_value("Person", mine.name, "church"), self.branch_b)

	def test_a_transfer_between_the_churches_you_hold_still_moves_the_person(self):
		moving = make_person("_Test Boundary Moving", "Person", church=self.branch_a)
		parent = self.bind_manager("_test_boundary_parent@example.com", "BoundaryParent", self.root)
		permission = frappe.get_all(
			"User Permission", filters={"user": parent, "allow": "Church"}, pluck="name"
		)[0]
		frappe.db.set_value("User Permission", permission, "hide_descendants", 0)

		frappe.set_user(parent)
		frappe.clear_cache(user=parent)
		self.transfer(moving.name, self.branch_b)

		self.assertEqual(frappe.db.get_value("Person", moving.name, "church"), self.branch_b)

	def test_the_sign_up_helpers_refuse_another_churchs_function(self):
		item = ensure("Sign-Up Item", {"item": "_Test Boundary Casserole"})
		function = make_function("_Test Boundary Function", church=self.branch_a)
		function.append("table_cxhh", {"item": item, "quantity_needed": 7})
		function.allow_sign_ups = 1
		function.save(ignore_permissions=True)

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			get_function_item_totals(function.name)
		with self.assertRaises(frappe.PermissionError):
			get_item_status(function.name, item)

	def test_an_email_group_cannot_be_built_from_another_churchs_group(self):
		"""The members' email addresses would land in an Email Group with no church."""
		member = make_person("_Test Boundary Member", "One", church=self.branch_a)
		member.append("emails", {"email_address": "_test_boundary_member@example.com", "is_primary": 1})
		member.save(ignore_permissions=True)
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Boundary Group",
				"church": self.branch_a,
				"members": [{"person": member.name}],
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			create_email_group(group.name)

	def test_the_comment_card_counts_only_the_readers_prayer_requests(self):
		"""Comment carries no church, so the count is anchored to the request."""
		request_type = ensure("Prayer Request Type", {"type": "_Test Boundary Type"})
		for church in (self.branch_a, self.branch_b):
			request = frappe.get_doc(
				{
					"doctype": "Prayer Request",
					"title": f"_Test Boundary Request {church}",
					"type": request_type,
					"church": church,
					"date": nowdate(),
				}
			).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"reference_doctype": "Prayer Request",
					"reference_name": request.name,
					"content": "_Test Boundary comment",
				}
			).insert(ignore_permissions=True)

		frappe.set_user(self.manager_b)
		mine = prayer_request_comments.get_count()
		frappe.set_user("Administrator")

		self.assertEqual(mine, 1, "another church's prayer request comments reached this count")

	def function_with_a_regular(self, name):
		"""A branch A function with one of branch A's people in its attendance."""
		function = make_function(name, church=self.branch_a, description="_Test Boundary plan")
		regular = make_person("_Test Boundary", "Regular", church=self.branch_a)
		function.append("attendance", {"person": regular.name, "attendance_type": "Assumed"})
		function.save(ignore_permissions=True)
		return function

	def test_a_function_that_is_no_template_cannot_be_copied_from_another_church(self):
		"""Naming any function handed over its plan and its attendance list."""
		function = self.function_with_a_regular("_Test Boundary Private Plan")

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			apply_template(function.name)

	def test_another_churchs_template_arrives_without_its_people(self):
		"""Templates are shared on purpose; with a private directory, the regulars who came with it are not."""
		self.keep_people_private()
		template = self.function_with_a_regular("_Test Boundary Shared Template")
		ensure(
			"Function Type",
			{"type": "_Test Boundary Template Type"},
			{"type": "_Test Boundary Template Type", "template_function": template.name},
		)

		frappe.set_user(self.manager_b)
		copied = apply_template(template.name)

		self.assertEqual(copied["description"], "_Test Boundary plan")
		self.assertEqual(copied["attendance"], [])

	def test_a_member_cannot_join_another_churchs_public_group(self):
		"""The portal lists only the member's own groups; the call itself has to agree."""
		ensure("Group Role", {"role": "Member"})
		theirs = self.portal_group("_Test Boundary Their Group", self.branch_a)
		mine = self.portal_group("_Test Boundary My Group", self.branch_b)

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.ValidationError):
			join_group(theirs)
		self.assertEqual(join_group(mine)["joined"], True)
		self.assertFalse(frappe.db.exists("Group Member", {"parent": theirs}))

	def portal_group(self, name, church):
		return (
			frappe.get_doc(
				{"doctype": "Group", "group_name": name, "church": church, "public": 1, "show_in_portal": 1}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_check_in_refuses_another_churchs_function_or_people(self):
		"""The check-ins are inserted with ignore_permissions, so the call checks both links."""
		self.keep_people_private()
		their_function = make_function("_Test Boundary Their Service", church=self.branch_a).name
		my_function = make_function("_Test Boundary My Service", church=self.branch_b).name
		their_person = make_person("_Test Boundary Their", "Attender", church=self.branch_a).name
		my_person = make_person("_Test Boundary My", "Attender", church=self.branch_b).name

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			check_in_persons(their_function, [my_person])
		with self.assertRaises(frappe.PermissionError):
			check_in_persons(my_function, [my_person, their_person])
		self.assertFalse(frappe.db.exists("Function Check-In", {"person": their_person}))
		self.assertEqual(len(check_in_persons(my_function, [my_person])), 1)

	def test_a_manager_cannot_sign_up_another_churchs_private_person(self):
		self.keep_people_private()
		function = make_function("_Test Boundary Sign-Up Service", church=self.branch_b, allow_sign_ups=1)
		theirs = make_person("_Test Boundary Their", "Volunteer", church=self.branch_a).name

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{"doctype": "Function Sign-Up", "function": function.name, "person": theirs}
			).insert()

	def test_a_shared_service_station_finds_and_checks_in_every_churchs_people(self):
		"""Even with a private directory, a joint service's station has to find whoever walks in."""
		self.keep_people_private()
		joint = make_function("_Test Boundary Joint Service", church=self.branch_a, is_shared=1).name
		my_service = make_function("_Test Boundary Branch Service", church=self.branch_b).name
		visitor = make_person("_Test Boundary Jointvisitor", "Guest", church=self.branch_a).name

		frappe.set_user(self.manager_b)
		self.assertEqual(self.station_finds("Jointvisitor", joint), [visitor])
		self.assertEqual(self.station_finds("Jointvisitor", my_service), [])
		self.assertEqual(self.station_finds("Jointvisitor", None), [])

		check_in_persons(joint, [visitor])
		frappe.set_user(self.manager_a)
		self.assertEqual([row.person for row in get_check_ins(joint)], [visitor])

	def station_finds(self, query, function):
		groups = search_people(query, function)
		return [member.name for group in groups for member in group["members"]]

	def test_the_roster_of_another_churchs_service_is_refused(self):
		their_service = make_function("_Test Boundary Their Roster", church=self.branch_a).name

		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			get_check_ins(their_service)
		with self.assertRaises(frappe.PermissionError):
			search_people("Anyone", their_service)
