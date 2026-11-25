# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries import pre_check_in
from churchit.church_ministries.doctype.function_check_in.function_check_in import add_check_ins
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.church_website.pages import sync_page_switches
from churchit.portal import home, household
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_address,
	make_function,
	make_person,
	make_two_churches,
)

DAY = "2031-05-01"


def switch_page(route, enabled):
	features = frappe.get_single("Church Features")
	features.get("website_pages", {"route": route})[0].enabled = enabled
	features.save()


class TestHouseholdApi(RollbackEachTest):
	"""The Smiths of church A: John and Jane (Adults), Tim (Child, 10), Gran (Other Adult); and one family of church B."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		sync_page_switches()
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household(
			"_Test Portal Household"
		)
		frappe.db.set_value("Family", cls.family, "church", cls.branch_a)
		frappe.db.set_value("Person", {"family": cls.family}, "church", cls.branch_a)
		cls.father_user = link_user(cls.father, "_test_portal_household_father@example.com")
		cls.mother_user = link_user(cls.mother, "_test_portal_household_mother@example.com")
		cls.son_user = link_user(cls.son, "_test_portal_household_son@example.com")
		for user in (cls.father_user, cls.mother_user, cls.son_user):
			set_user_church(user, cls.branch_a)

		other = make_household("_Test Portal Other", "Jones")
		cls.other_family, cls.other_father = other[0], other[1]
		frappe.db.set_value("Family", cls.other_family, "church", cls.branch_b)
		frappe.db.set_value("Person", {"family": cls.other_family}, "church", cls.branch_b)

		cls.self_type = ensure("Function Type", {"type": "_Test Portal Household Type"})
		frappe.db.set_value("Function Type", cls.self_type, "allow_self_check_in", 1)
		cls.function = make_function(
			"_Test Portal Household Class",
			type=cls.self_type,
			church=cls.branch_a,
			start_date=DAY,
			start_time="10:00:00",
			end_time="11:00:00",
		).name
		frappe.get_single("Check-In Settings").save(ignore_permissions=True)
		frappe.db.set_single_value(
			"Check-In Settings",
			{"check_in_opens_minutes": 60, "security_codes": 0, "adults_pre_check_in_adults": 0},
		)

	def setUp(self):
		super().setUp()
		moment = get_datetime(f"{DAY} 09:30")
		for target in ("check_in_limits.now_datetime", "pre_check_in.now_datetime"):
			self.enterContext(patch(f"churchit.church_ministries.{target}", return_value=moment))
		self.enterContext(patch("churchit.church_ministries.kiosk.today", return_value=DAY))
		self.enterContext(patch.object(pre_check_in, "get_qr_code", side_effect=lambda value: value))

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_the_household_has_display_fields_and_the_members_the_adult_may_edit(self):
		frappe.set_user(self.father_user)
		result = household.get_household()

		self.assertEqual(result["family"]["name"], self.family)
		self.assertEqual(result["family"]["title"], "The _Test Portal Household Family")
		self.assertEqual(
			set(result["family"]), {"name", "title", "photo", "address"}, "only display fields of the Family"
		)
		by_name = {row["name"]: row for row in result["members"]}
		self.assertTrue(by_name[self.father]["is_you"])
		self.assertTrue(by_name[self.son]["can_edit"])
		self.assertEqual(by_name[self.son]["age"], 10)
		self.assertFalse(by_name[self.mother]["can_edit"])
		self.assertEqual(result["add_child"]["adult_age"], 18)
		self.assertTrue(result["can_change_photo"])

	def test_a_child_gets_no_add_child_form_and_no_photo_change(self):
		frappe.set_user(self.son_user)
		result = household.get_household()

		self.assertIsNone(result["add_child"])
		self.assertFalse(result["can_change_photo"])

	def test_the_household_never_shows_another_family(self):
		frappe.set_user(self.father_user)
		names = {row["name"] for row in household.get_household()["members"]}

		self.assertNotIn(self.other_father, names)

	def test_the_members_come_with_their_roles_primary_contact_first(self):
		frappe.set_user(self.son_user)
		rows = household.get_household()["members"]

		self.assertEqual(
			[(row["name"], row["household_role"]) for row in rows],
			[
				(self.father, "Adult"),
				(self.mother, "Adult"),
				(self.son, "Child"),
				(self.grandmother, "Other Adult"),
			],
		)
		self.assertEqual(rows[0]["display_name"], "John Smith")

	def test_only_a_childs_known_age_shows(self):
		frappe.set_user(self.son_user)
		ages = {row["name"]: row["age"] for row in household.get_household()["members"]}

		self.assertEqual(ages, {self.father: None, self.mother: None, self.son: 10, self.grandmother: None})

	def test_someone_who_has_died_is_not_listed(self):
		frappe.db.set_value("Person", self.grandmother, "is_deceased", 1)
		frappe.set_user(self.son_user)

		self.assertNotIn(self.grandmother, {row["name"] for row in household.get_household()["members"]})

	def test_the_family_shows_its_mailing_address(self):
		address = make_address("_Test Portal Household Home", address_line1="230 Walnut Street")
		family = frappe.get_doc("Family", self.family)
		family.append("addresses", {"address": address.name, "is_mailing_address": 1})
		family.save(ignore_permissions=True)
		frappe.set_user(self.son_user)

		self.assertEqual(household.get_household()["family"]["address"], "230 Walnut Street, Springfield")

	def test_the_edit_answer_matches_frappes_permission_for_every_member(self):
		staff = ensure_user("_test_portal_household_staff@example.com", "Staff", roles=("Church Manager",))
		grandmother_user = link_user(self.grandmother, "_test_portal_household_gran@example.com")
		people = [self.father, self.mother, self.son, self.grandmother]
		for user in (self.father_user, self.mother_user, self.son_user, grandmother_user, staff):
			frappe.set_user(user)
			expected = {name: frappe.has_permission("Person", "write", doc=name) for name in people}
			found = {member.name: member.can_edit for member in household.get_members(people, {})}
			self.assertEqual(found, expected, user)

	def test_an_adult_may_not_edit_a_child_of_another_church(self):
		frappe.db.set_value("Person", self.son, "church", self.branch_b)
		frappe.set_user(self.father_user)
		rows = household.get_household()["members"]

		self.assertFalse(frappe.has_permission("Person", "write", doc=self.son))
		self.assertEqual({row["name"] for row in rows if row["can_edit"]}, {self.father})

	def test_a_member_without_the_member_role_may_edit_no_one(self):
		user = ensure_user("_test_portal_household_no_role@example.com", "Jane", roles=())
		frappe.db.set_value("Person", self.mother, "user", user)
		frappe.set_user(user)

		self.assertEqual([row for row in household.get_household()["members"] if row["can_edit"]], [])

	def test_a_member_without_a_family_sees_only_themselves(self):
		user = ensure_user("_test_portal_household_single@example.com", "Single")
		person = make_person("_Test Portal Household", "Single", user=user, church=self.branch_a).name
		frappe.set_user(user)
		result = household.get_household()

		self.assertIsNone(result["family"])
		self.assertEqual([row["name"] for row in result["members"]], [person])

	def test_a_login_with_no_person_is_refused(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			household.get_household()

	def test_a_switched_off_page_is_refused(self):
		switch_page("household", 0)
		frappe.set_user(self.father_user)

		for endpoint in (household.get_household, household.get_pre_check_in):
			with self.assertRaises(frappe.PermissionError):
				endpoint()

		with self.assertRaises(frappe.PermissionError):
			household.get_check_in_code(self.function, frappe.as_json([self.father]))

	def test_pre_check_in_offers_the_open_function_and_the_people_the_adult_may_check_in(self):
		frappe.set_user(self.father_user)
		result = household.get_pre_check_in()

		self.assertEqual([row["name"] for row in result["functions"]], [self.function])
		self.assertEqual(result["functions"][0]["time"], "10:00 AM")
		self.assertEqual(result["functions"][0]["start_time"], "10:00:00")
		people = {row["name"] for row in result["people"]}
		self.assertEqual(people, {self.father, self.son})
		self.assertIsNone(result["opens_minutes"])

	def test_pre_check_in_adds_the_other_adults_when_settings_allow_it(self):
		frappe.db.set_single_value("Check-In Settings", "adults_pre_check_in_adults", 1)
		frappe.set_user(self.father_user)
		people = {row["name"] for row in household.get_pre_check_in()["people"]}

		self.assertEqual(people, {self.father, self.mother, self.son, self.grandmother})

	def test_pre_check_in_says_who_is_in_already(self):
		add_check_ins(self.function, [self.son])
		frappe.set_user(self.father_user)
		by_name = {row["name"]: row for row in household.get_pre_check_in()["people"]}

		self.assertIn(self.function, by_name[self.son]["checked_in"])
		self.assertEqual(by_name[self.father]["checked_in"], {})

	def test_pre_check_in_says_when_check_in_opens_when_no_function_is_open(self):
		self.enterContext(
			patch(
				"churchit.church_ministries.check_in_limits.now_datetime",
				return_value=get_datetime(f"{DAY} 06:00"),
			)
		)
		frappe.set_user(self.father_user)
		result = household.get_pre_check_in()

		self.assertEqual(result["functions"], [])
		self.assertEqual(result["opens_minutes"], 60)

	def test_the_home_page_offers_the_check_in_of_the_household_page(self):
		frappe.set_user(self.father_user)
		check_in = home.get_check_in(self.father)

		self.assertEqual([row["name"] for row in check_in["functions"]], [self.function])
		self.assertEqual(check_in["functions"][0]["time"], "10:00:00")
		self.assertEqual({row["name"] for row in check_in["people"]}, {self.father, self.son})

	def test_the_home_page_offers_no_check_in_while_no_function_is_open(self):
		self.enterContext(
			patch(
				"churchit.church_ministries.check_in_limits.now_datetime",
				return_value=get_datetime(f"{DAY} 06:00"),
			)
		)
		frappe.set_user(self.father_user)

		self.assertIsNone(home.get_check_in(self.father))

	def test_the_code_checks_the_right_to_check_each_person_in(self):
		frappe.set_user(self.father_user)
		result = household.get_check_in_code(self.function, frappe.as_json([self.father, self.son]))
		self.assertIn("qr_code", result)
		self.assertEqual(result["valid_until"], "11:00 AM")

		with self.assertRaises(frappe.PermissionError):
			household.get_check_in_code(self.function, frappe.as_json([self.mother]))
		with self.assertRaises(frappe.PermissionError):
			household.get_check_in_code(self.function, frappe.as_json([self.other_father]))

	def test_a_function_that_is_not_offered_gets_no_code(self):
		other = make_function(
			"_Test Portal Other Class",
			type=self.self_type,
			church=self.branch_b,
			start_date=DAY,
			start_time="10:00:00",
			end_time="11:00:00",
		).name
		frappe.set_user(self.father_user)

		for function in (other, "FUNC-DOES-NOT-EXIST"):
			with self.assertRaises(frappe.PermissionError):
				household.get_check_in_code(function, frappe.as_json([self.father]))

	def test_the_pass_names_the_rooms_booked_for_the_function(self):
		room = ensure(
			"Room",
			{"room_name": "_Test Portal Room 104"},
			{"room_name": "_Test Portal Room 104", "church": self.branch_a},
		)
		requester = make_person("Booker", "_Test Portal Household").name
		frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": requester,
				"purpose": "_Test portal check-in",
				"start_datetime": f"{DAY} 09:00:00",
				"end_datetime": f"{DAY} 10:00:00",
				"function": self.function,
				"status": "Approved",
				"church": self.branch_a,
			}
		).insert(ignore_permissions=True)
		frappe.set_user(self.father_user)

		self.assertEqual(household.get_pre_check_in()["functions"][0]["rooms"], ["_Test Portal Room 104"])

	def test_a_booking_without_a_room_or_a_second_booking_of_one_room_does_not_break_the_pass(self):
		room = ensure(
			"Room",
			{"room_name": "_Test Portal Room 105"},
			{"room_name": "_Test Portal Room 105", "church": self.branch_a},
		)
		asset = frappe.get_doc(
			{
				"doctype": "Church Asset",
				"title": "_Test Portal Projector",
				"church": self.branch_a,
				"is_bookable": 1,
			}
		).insert(ignore_permissions=True)
		requester = make_person("Booker", "_Test Portal Household").name
		booking = {
			"doctype": "Room Booking",
			"requester": requester,
			"purpose": "_Test portal check-in",
			"function": self.function,
			"status": "Approved",
			"church": self.branch_a,
		}
		slots = (
			({"room": room}, "09:00", "10:00"),
			({"room": room}, "11:00", "12:00"),
			({"assets": [{"asset": asset.name}]}, "13:00", "14:00"),
		)
		for values, start, end in slots:
			frappe.get_doc(
				{
					**booking,
					**values,
					"start_datetime": f"{DAY} {start}:00",
					"end_datetime": f"{DAY} {end}:00",
				}
			).insert(ignore_permissions=True)
		frappe.set_user(self.father_user)

		self.assertEqual(household.get_pre_check_in()["functions"][0]["rooms"], ["_Test Portal Room 105"])

	def test_the_pass_says_whether_pickup_codes_are_used(self):
		frappe.set_user(self.father_user)
		frappe.db.set_single_value("Check-In Settings", "security_codes", 0)
		self.assertFalse(household.get_pre_check_in()["has_pickup_codes"])
		frappe.db.set_single_value("Check-In Settings", "security_codes", 1)
		self.assertTrue(household.get_pre_check_in()["has_pickup_codes"])

	def test_a_check_in_tells_the_household_adults_and_the_person(self):
		with patch("churchit.portal.realtime.frappe.publish_realtime") as publish:
			check_in = add_check_ins(self.function, [self.son])[0]

		calls = [call for call in publish.call_args_list if call.args[0] == "churchit_portal"]
		users = {call.kwargs["user"] for call in calls}
		self.assertEqual(users, {self.father_user, self.mother_user, self.son_user})
		for call in calls:
			self.assertEqual(call.args, ("churchit_portal", {"topic": "check-in", "name": check_in}))
			self.assertTrue(call.kwargs["after_commit"])

	def test_a_change_to_the_family_tells_the_adults(self):
		force_single_church()
		family = frappe.get_doc("Family", self.family)
		with patch("churchit.portal.realtime.frappe.publish_realtime") as publish:
			family.save(ignore_permissions=True)

		topics = {
			(call.args[1]["topic"], call.kwargs["user"])
			for call in publish.call_args_list
			if call.args[0] == "churchit_portal"
		}
		self.assertIn(("household", self.father_user), topics)
		self.assertIn(("household", self.mother_user), topics)
		self.assertNotIn(("household", self.son_user), topics)
