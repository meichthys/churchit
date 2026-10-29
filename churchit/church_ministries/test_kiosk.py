# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import Mock, patch

import frappe
from frappe.api.v1 import document_list, read_doc
from frappe.permissions import add_user_permission
from frappe.utils import get_datetime

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.check_in_limits import RoomFullError, is_check_in_open
from churchit.church_ministries.doctype.function_check_in.function_check_in import add_check_ins
from churchit.church_ministries.kiosk import KIOSK_ROLE, check_in, find_household
from churchit.church_people.accounts import link_portal_user
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
	set_private_people,
)
from churchit.www import check_in_kiosk

DAY = "2031-05-01"
PHONE = "(555) 019-4321"


class TestKiosk(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.kiosk = ensure_user("_test_kiosk_a@example.com", "Kiosk", roles=(KIOSK_ROLE,))
		set_user_church(cls.kiosk, cls.branch_a)
		cls.volunteer = ensure_user("_test_kiosk_volunteer@example.com", "Kiosk", roles=("Church Check-In",))
		set_user_church(cls.volunteer, cls.branch_a)

		cls.self_type = ensure("Function Type", {"type": "_Test Kiosk Type"})
		frappe.db.set_value("Function Type", cls.self_type, "allow_self_check_in", 1)
		cls.function = cls.make_class("_Test Kiosk Class")
		cls.family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Kiosk Family", "church": cls.branch_a}
		).insert(ignore_permissions=True)
		cls.parent = cls.make_member("Kim", phones=[{"phone_number": PHONE, "is_primary": 1}]).name
		cls.child = cls.make_member("Kit", photo="/files/kit.jpg", graduation_year=2036).name
		cls.sibling = cls.make_member("Kai").name
		cls.loner = make_person("Lone", "_Test Kiosk", church=cls.branch_a).name

		frappe.get_single("Check-In Settings").save(ignore_permissions=True)
		frappe.db.set_single_value(
			"Check-In Settings", {"check_in_opens_minutes": 60, "capacity_mode": "Warn"}
		)

	@classmethod
	def make_class(cls, name, **values):
		return make_function(
			name,
			type=cls.self_type,
			church=cls.branch_a,
			start_date=DAY,
			start_time="10:00:00",
			end_time="11:00:00",
			**values,
		).name

	@classmethod
	def make_member(cls, first_name, **values):
		return make_person(first_name, "_Test Kiosk", family=cls.family.name, church=cls.branch_a, **values)

	def setUp(self):
		super().setUp()
		self.at("09:30")
		self.enterContext(patch.object(frappe.db, "commit"))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def at(self, time):
		"""Run the rest of the test at *time* on DAY."""
		moment = get_datetime(f"{DAY} {time}")
		self.enterContext(
			patch("churchit.church_ministries.check_in_limits.now_datetime", return_value=moment)
		)
		self.enterContext(patch("churchit.church_ministries.kiosk.today", return_value=DAY))

	def find(self, phone=PHONE):
		frappe.set_user(self.kiosk)
		try:
			return find_household(phone)
		finally:
			frappe.set_user("Administrator")

	def check_in(self, choices, phone=PHONE):
		frappe.set_user(self.kiosk)
		try:
			return check_in(phone, json.dumps(choices))
		finally:
			frappe.set_user("Administrator")

	def members(self, found):
		return {
			member["name"]: member["functions"]
			for group in found["households"]
			for member in group["members"]
		}

	def test_a_kiosk_session_cannot_read_people_over_rest(self):
		self.assertEqual(frappe.db.get_value("User", self.kiosk, "user_type"), "Website User")
		frappe.set_user(self.kiosk)
		frappe.local.form_dict = frappe._dict()
		self.assertRaises(frappe.PermissionError, document_list, "Person")
		self.assertRaises(frappe.PermissionError, read_doc, "Person", self.child)

	def test_a_kiosk_sign_in_adds_no_person(self):
		frappe.set_user(self.kiosk)
		link_portal_user()
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Person", {"user": self.kiosk}))

	def test_a_check_in_locks_the_function_then_the_code_then_the_check_ins(self):
		locks = Mock()
		for method in ("get_value", "get_single_value", "get_values"):
			locks.attach_mock(
				self.enterContext(patch.object(frappe.db, method, wraps=getattr(frappe.db, method))), method
			)

		self.check_in({self.child: self.function})

		locked = [call.args[0] for call in locks.mock_calls if call.kwargs.get("for_update")]
		self.assertEqual(list(dict.fromkeys(locked)), ["Function", "Check-In Settings", "Function Check-In"])

	def test_a_whole_phone_number_finds_the_household_with_names_photos_and_grades_only(self):
		found = self.find()

		self.assertEqual([{"name", "function_name", "start_time"}], [set(row) for row in found["functions"]])
		(household,) = found["households"]
		self.assertEqual(household["family_name"], "_Test Kiosk Family")
		kit = next(member for member in household["members"] if member["name"] == self.child)
		self.assertEqual(set(kit), {"name", "full_name", "photo", "grade", "functions"})
		self.assertEqual(kit["photo"], "/files/kit.jpg")
		self.assertEqual(kit["grade"], frappe.db.get_value("Person", self.child, "grade"))
		self.assertEqual(
			self.members(found),
			{person: [self.function] for person in (self.parent, self.child, self.sibling)},
		)

	def test_a_private_photo_is_not_sent(self):
		frappe.db.set_value("Person", self.child, "photo", "/private/files/kit.jpg")
		kit = next(
			member
			for household in self.find()["households"]
			for member in household["members"]
			if member["name"] == self.child
		)
		self.assertIsNone(kit["photo"])

	def test_a_familys_phone_finds_its_members(self):
		frappe.db.set_value(
			"Phone Number", {"parent": self.parent}, {"parenttype": "Family", "parent": self.family.name}
		)
		self.assertEqual(set(self.members(self.find())), {self.parent, self.child, self.sibling})

	def test_a_partial_phone_number_or_a_person_id_finds_nobody(self):
		for lookup in ("0194321", "5550194", "555 019 43210", self.child, ""):
			found = self.find(lookup)
			self.assertEqual(found["households"], [], lookup)
			self.assertEqual([row["name"] for row in found["functions"]], [self.function], lookup)

	def test_a_function_whose_type_does_not_allow_self_check_in_is_refused(self):
		staffed = make_function(
			"_Test Kiosk Staffed", church=self.branch_a, start_date=DAY, start_time="10:00"
		)
		self.assertNotIn(staffed.name, {row["name"] for row in self.find()["functions"]})
		self.assertRaises(frappe.PermissionError, self.check_in, {self.child: staffed.name})
		self.assertFalse(frappe.db.exists("Function Check-In", {"function": staffed.name}))

	def test_a_function_outside_its_window_is_refused(self):
		for time in ("08:59", "11:01"):
			self.at(time)
			self.assertEqual(self.find(), {"functions": [], "households": []}, time)
			self.assertRaises(frappe.PermissionError, self.check_in, {self.child: self.function})

	def test_check_in_opens_the_set_minutes_before_the_start_and_closes_at_the_end(self):
		frappe.db.set_single_value("Check-In Settings", "check_in_opens_minutes", 15)
		for time, is_open in (("09:44", False), ("09:45", True), ("11:00", True), ("11:01", False)):
			self.at(time)
			self.assertEqual(is_check_in_open(self.function), is_open, time)

		all_day = self.make_class("_Test Kiosk All Day", all_day=1)
		self.at("06:00")
		self.assertTrue(is_check_in_open(all_day))

	def test_a_check_in_is_regular_and_prints_through_the_churchs_printer(self):
		settings = frappe.get_single("Check-In Settings")
		settings.append(
			"printers",
			{
				"church": self.branch_a,
				"name_tag_printing": "Zebra Browser Print",
				"printer_name": "_Test Kiosk Zebra",
			},
		)
		settings.save(ignore_permissions=True)

		result = self.check_in({self.child: self.function})

		check_in = frappe.get_doc("Function Check-In", {"function": self.function, "person": self.child})
		self.assertEqual(check_in.check_in_kind, "Regular")
		self.assertEqual(result["count"], 1)
		self.assertEqual(result["print"]["method"], "Zebra Browser Print")
		self.assertEqual(result["print"]["printer_name"], "_Test Kiosk Zebra")
		self.assertIn("^XA", result["print"]["content"])

	def test_a_second_check_in_prints_nothing(self):
		self.check_in({self.child: self.function})
		result = self.check_in({self.child: self.function, self.sibling: self.function})
		self.assertEqual(result["print"]["count"], 1)
		self.assertIsNone(self.check_in({self.child: self.function})["print"])

	def test_a_kiosk_prints_a_new_code_but_never_one_the_household_already_holds(self):
		frappe.db.set_single_value("Check-In Settings", "security_codes", 1)
		result = self.check_in({self.sibling: self.function})
		code = frappe.db.get_value(
			"Function Check-In", {"function": self.function, "person": self.sibling}, "security_code"
		)
		self.assertIn(code, result["print"]["content"])
		self.assertFalse(result["has_earlier_code"])

		staffed = make_function(
			"_Test Kiosk Staffed", church=self.branch_a, start_date=DAY, start_time="10:00"
		)
		(earlier,) = add_check_ins(staffed.name, [self.child])
		self.assertEqual(frappe.db.get_value("Function Check-In", earlier, "security_code"), code)
		result = self.check_in({self.parent: self.function})

		self.assertNotIn(code, result["print"]["content"])
		self.assertTrue(result["has_earlier_code"])
		self.assertEqual(
			frappe.db.get_value(
				"Function Check-In", {"function": self.function, "person": self.parent}, "security_code"
			),
			code,
		)

	def test_a_kiosk_without_exactly_one_church_is_refused(self):
		self.addCleanup(frappe.clear_cache, user=self.kiosk)
		frappe.local.form_dict = frappe._dict(church=self.branch_b)
		add_user_permission("Church", self.branch_b, self.kiosk, ignore_permissions=True)
		frappe.db.set_value("User Permission", {"user": self.kiosk, "allow": "Church"}, "is_default", 0)
		frappe.clear_cache(user=self.kiosk)
		self.assertRaises(frappe.PermissionError, self.find)
		self.assertRaises(frappe.PermissionError, self.check_in, {self.child: self.function})

		frappe.db.delete("User Permission", {"user": self.kiosk, "allow": "Church"})
		frappe.clear_cache(user=self.kiosk)
		self.assertRaises(frappe.PermissionError, self.find)

	def test_a_person_the_phone_did_not_find_is_refused(self):
		self.assertRaises(frappe.PermissionError, self.check_in, {self.loner: self.function})
		for choices in ({}, [self.child], {self.child: [self.function]}):
			self.assertRaises(frappe.PermissionError, self.check_in, choices)

	def test_block_mode_refuses_a_full_room(self):
		frappe.db.set_single_value("Check-In Settings", "capacity_mode", "Block")
		room = ensure(
			"Room",
			{"room_name": "_Test Kiosk Room"},
			{"room_name": "_Test Kiosk Room", "capacity": 1, "is_bookable": 1},
		)
		frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.parent,
				"purpose": "_Test kiosk",
				"start_datetime": f"{DAY} 10:00:00",
				"end_datetime": f"{DAY} 11:00:00",
				"function": self.function,
				"status": "Approved",
			}
		).insert(ignore_permissions=True)

		self.check_in({self.child: self.function})
		self.assertRaises(RoomFullError, self.check_in, {self.sibling: self.function})

	def test_a_child_outside_the_bounds_is_not_offered_that_function(self):
		bounded = self.make_class("_Test Kiosk Toddlers", max_age=3)
		offered = self.members(self.find())
		self.assertEqual(offered[self.child], [self.function])
		self.assertRaises(frappe.PermissionError, self.check_in, {self.child: bounded})

	def test_with_private_people_another_churchs_household_comes_only_to_a_shared_function(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		frappe.db.set_value("Person", {"family": self.family.name}, "church", self.branch_b)
		self.assertEqual(self.find()["households"], [])

		joint = self.make_class("_Test Kiosk Joint", is_shared=1)
		self.assertEqual(self.members(self.find())[self.child], [joint])
		self.assertRaises(frappe.PermissionError, self.check_in, {self.child: self.function})

	def test_single_church_mode_still_finds_the_household(self):
		force_single_church()
		self.assertEqual(self.members(self.find())[self.child], [self.function])

	def test_only_a_kiosk_may_call(self):
		frappe.set_user(self.volunteer)
		self.assertRaises(frappe.PermissionError, find_household, PHONE)
		self.assertRaises(frappe.PermissionError, check_in, PHONE, json.dumps({self.child: self.function}))

	def test_the_page_sends_guests_to_sign_in_and_refuses_everyone_but_a_kiosk(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.Redirect, check_in_kiosk.get_context, frappe._dict())
		frappe.set_user(self.volunteer)
		self.assertRaises(frappe.PermissionError, check_in_kiosk.get_context, frappe._dict())

		frappe.set_user(self.kiosk)
		context = frappe._dict()
		check_in_kiosk.get_context(context)
		self.assertEqual(context.church_name, "_Test Scope A")
