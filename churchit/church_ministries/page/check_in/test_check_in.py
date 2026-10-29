# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, now_datetime

from churchit.church_ministries.page.check_in.check_in import (
	add_visitor,
	check_in,
	find_card_holder,
	get_check_ins,
	get_pickup_families,
	get_station_context,
	search_people,
	undo_check_in,
)
from churchit.church_ministries.page.check_in.checkout import check_out
from churchit.church_people.doctype.family.test_pickup_scope import make_pickup
from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.test_household import make_household, set_adult_age
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_function,
	make_person,
	make_primary_contact,
	set_multi_church,
	set_private_people,
)

STATION = "churchit.church_ministries.page.check_in.check_in"


def check_in_with_code(function, person, code):
	return frappe.get_doc(
		{"doctype": "Function Check-In", "function": function, "person": person, "security_code": code}
	).insert(ignore_permissions=True)


class TestCheckInStation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.function = make_function("_Test Station Function", start_date=frappe.utils.today())
		cls.family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Zebrastripe"}).insert(
			ignore_permissions=True
		)
		cls.parent = make_primary_contact(
			make_person(
				"Zed",
				"Zebrastripe",
				family=cls.family.name,
				phones=[{"phone_number": "(555) 010-9876", "is_primary": 1}],
			)
		)
		cls.child = make_person("Zoe", "Zebrastripe", family=cls.family.name, photo="/files/zoe.jpg")
		ensure("Life Event Type", {"type": "Death"})
		make_person(
			"Zara",
			"Zebrastripe",
			family=cls.family.name,
			life_events=[{"event_type": "Death", "date": "2024-01-01"}],
		)
		cls.loner = make_person("Zack", "Zebraless")
		frappe.get_single("Check-In Settings").save(ignore_permissions=True)

	def members_of(self, groups):
		return [[m.first_name for m in group["members"]] for group in groups]

	def test_name_search_expands_matches_to_the_whole_family(self):
		groups = search_people("zoe")
		self.assertEqual(self.members_of(groups), [["Zed", "Zoe"]])
		self.assertEqual([m.matched for m in groups[0]["members"]], [False, True])
		self.assertEqual([m.photo for m in groups[0]["members"]], [None, "/files/zoe.jpg"])
		self.assertEqual(groups[0]["family_name"], "_Test Zebrastripe")

	def test_search_matches_every_word_against_name_or_family(self):
		self.assertEqual(self.members_of(search_people("zack zebral")), [["Zack"]])
		self.assertEqual(self.members_of(search_people("zebra")), [["Zack"], ["Zed", "Zoe"]])
		self.assertEqual(self.members_of(search_people("zebrastripe zoe")), [["Zed", "Zoe"]])

	def test_search_matches_a_nickname(self):
		make_person("Margaret", "_Test Nickname", nickname="Peggy")
		self.assertEqual(self.members_of(search_people("peggy")), [["Margaret"]])

	def test_phone_search_ignores_formatting(self):
		self.assertEqual(self.members_of(search_people("5550109876")), [["Zed", "Zoe"]])
		self.assertEqual(self.members_of(search_people("010-98")), [["Zed", "Zoe"]])

	def test_people_who_have_died_are_left_out(self):
		"""A match is expanded to the whole family, which brought a late grandparent to the station."""
		self.assertEqual(self.members_of(search_people("zebrastripe")), [["Zed", "Zoe"]])
		self.assertEqual(search_people("zara"), [])

	def test_short_queries_return_nothing(self):
		self.assertEqual(search_people("z"), [])
		self.assertEqual(search_people("  "), [])

	def test_station_context_lists_functions_around_today(self):
		context = get_station_context()
		self.assertIn(self.function.name, [f.name for f in context["functions"]])
		self.assertEqual(context["name_tag_printing"], "Browser")

	def test_check_in_records_people_and_returns_a_print_job(self):
		with patch.object(frappe.db, "commit"):
			result = check_in(self.function.name, [self.parent.name, self.child.name], print_tags=1)
		self.assertEqual(len(result["check_ins"]), 2)
		self.assertEqual(result["print"]["count"], 2)
		roster = get_check_ins(self.function.name)
		self.assertEqual(sorted(row.full_name for row in roster), ["Zed Zebrastripe", "Zoe Zebrastripe"])

	def test_check_ins_are_committed_before_the_printer_is_reached(self):
		"""An unreachable network printer must not hold the check-in locks, nor lose the check-ins."""
		steps = []

		def print_to_a_printer_that_is_down(check_ins):
			steps.append("print")
			frappe.throw("Could not reach printer")

		with (
			patch.object(frappe.db, "commit", side_effect=lambda: steps.append("commit")),
			patch(f"{STATION}.print_name_tags", side_effect=print_to_a_printer_that_is_down),
			self.assertRaises(frappe.ValidationError),
		):
			check_in(self.function.name, [self.loner.name], print_tags=1)
		self.assertEqual(steps, ["commit", "print"])
		self.assertTrue(
			frappe.db.exists("Function Check-In", {"function": self.function.name, "person": self.loner.name})
		)

	def test_check_in_without_printing_returns_no_job(self):
		result = check_in(self.function.name, [self.loner.name])
		self.assertNotIn("print", result)

	def test_the_roster_carries_each_persons_photo(self):
		rosa = make_person("Rosa", "_Test Roster Photo", photo="/files/rosa.jpg").name
		check_in(self.function.name, [rosa])
		(row,) = [row for row in get_check_ins(self.function.name) if row.person == rosa]
		self.assertEqual(row.photo, "/files/rosa.jpg")

	def test_the_roster_says_who_left_when_and_who_collected_them(self):
		staying, leaving, collected = (
			make_person(name, "_Test Roster Checkout").name for name in ("Stan", "Lena", "Cole")
		)
		names = check_in(self.function.name, [staying, leaving, collected])["check_ins"]
		check_out(names[1])
		frappe.db.set_value(
			"Function Check-In",
			names[2],
			{"collected_at": now_datetime(), "collected_by": self.parent.name, "collected_by_name": "Zed"},
		)

		rows = {row.person: row for row in get_check_ins(self.function.name)}
		self.assertIsNone(rows[staying].collected_at)
		self.assertIsNotNone(rows[leaving].collected_at)
		self.assertIsNone(rows[leaving].collected_by_name)
		self.assertEqual(rows[collected].collected_by_name, "Zed")

	def test_undo_removes_the_check_in_and_attendance(self):
		name = check_in(self.function.name, [self.loner.name])["check_ins"][0]
		undo_check_in(name)
		self.assertFalse(frappe.db.exists("Function Check-In", name))
		attendance = frappe.get_doc("Function", self.function.name).attendance
		self.assertNotIn(self.loner.name, [row.person for row in attendance])

	def test_a_scanned_card_opens_the_holders_family_as_a_search_does(self):
		self.assertEqual(find_card_holder(self.child.name), search_people("zoe"))

	def test_a_card_of_someone_who_died_or_of_no_one_finds_nothing(self):
		dead = frappe.db.get_value("Person", {"first_name": "Zara", "last_name": "Zebrastripe"})
		self.assertEqual(find_card_holder(dead), [])
		self.assertEqual(find_card_holder("PRSN-NO-SUCH"), [])

	def test_add_visitor_creates_a_person_with_a_phone(self):
		visitor = add_visitor("Zelda", "Zebrastripe", phone="555 010 1111", family=self.family.name)
		person = frappe.get_doc("Person", visitor["name"])
		self.assertEqual(person.full_name, "Zelda Zebrastripe")
		self.assertEqual(person.family, self.family.name)
		self.assertEqual(person.phones[0].phone_number, "555 010 1111")
		self.assertEqual(person.source, "Check-In")
		self.assertEqual(self.members_of(search_people("0101111")), [["Zed", "Zelda", "Zoe"]])
		person.delete()

	def test_a_walk_in_is_a_visitor_who_shares_nothing(self):
		"""They never saw the directory's share choices, so the member directory must not list them."""
		person = frappe.get_doc("Person", add_visitor("Wanda", "Walkin", phone="555 010 2222")["name"])
		self.assertEqual(person.membership, "Visitor")
		self.assertEqual(
			{field: person.get(field) for field in SHARE_DEFAULTS}, dict.fromkeys(SHARE_DEFAULTS, 0)
		)
		person.delete()


class TestVerifyPickup(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		cls.function = make_function("_Test Pickup Service", start_date=frappe.utils.today())
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household(
			"_Test Pickup Household", "Pickupton"
		)
		aunt = ensure("Person Relation Type", {"type": "Aunt"})
		cls.aunt = make_person("Ada", "_Test Pickup Aunt", photo="/files/ada.jpg").name
		cls.late_uncle = make_person(
			"Ulric",
			"_Test Pickup Uncle",
			life_events=[{"event_type": ensure("Life Event Type", {"type": "Death"}), "date": "2024-01-01"}],
		).name
		make_pickup(cls.family, cls.aunt, relationship=aunt, notes="Sundays only")
		make_pickup(cls.family, cls.late_uncle)
		cls.check_in = check_in_with_code(cls.function.name, cls.son, "K7PX")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_code_shows_the_children_and_who_may_collect_them(self):
		(family,) = get_pickup_families(" k7px ")

		self.assertEqual(family["family_name"], "_Test Pickup Household")
		self.assertEqual(
			[(child.person, child.full_name, child.function_name) for child in family["children"]],
			[(self.son, "Tim Pickupton", "_Test Pickup Service")],
		)
		self.assertEqual([adult.name for adult in family["adults"]], [self.father, self.mother])
		self.assertEqual(
			[
				(row["person"], row["full_name"], row["relationship"], row["notes"], row["photo"])
				for row in family["pickups"]
			],
			[(self.aunt, "Ada _Test Pickup Aunt", "Aunt", "Sundays only", "/files/ada.jpg")],
		)

	def test_another_code_or_an_earlier_day_finds_no_child(self):
		self.assertEqual(get_pickup_families("ZZZZ"), [])

		yesterday = add_days(now_datetime(), -1)
		frappe.db.set_value(
			"Function Check-In", self.check_in.name, "creation", yesterday, update_modified=False
		)
		self.addCleanup(
			frappe.db.set_value,
			"Function Check-In",
			self.check_in.name,
			"creation",
			self.check_in.creation,
			update_modified=False,
		)
		self.assertEqual(get_pickup_families("K7PX"), [])

	def test_a_child_with_no_family_has_no_one_on_file(self):
		loner = make_person("Lonnie", "_Test Pickup Loner").name
		check_in_with_code(self.function.name, loner, "L9NE")

		(family,) = get_pickup_families("L9NE")

		self.assertEqual((family["family"], family["adults"], family["pickups"]), (None, [], []))
		self.assertEqual([child.person for child in family["children"]], [loner])

	def test_only_the_check_in_right_may_verify_a_pickup(self):
		staff = ensure_user("_test_pickup_staff@example.com", "PickupStaff", roles=("Church Staff",))
		volunteer = ensure_user(
			"_test_pickup_volunteer@example.com", "PickupVolunteer", roles=("Church Check-In",)
		)

		frappe.set_user(staff)
		with self.assertRaises(frappe.PermissionError):
			get_pickup_families("K7PX")

		frappe.set_user(volunteer)
		self.assertEqual(len(get_pickup_families("K7PX")), 1)


class TestStationBetweenChurches(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_root_church()
		set_multi_church(True)
		cls.branch_a = make_branch("_Test Station A", "TSTA")
		cls.branch_b = make_branch("_Test Station B", "TSTB")
		cls.volunteer_a = cls.bind_volunteer("_test_station_a@example.com", "StationA", cls.branch_a)
		cls.volunteer_b = cls.bind_volunteer("_test_station_b@example.com", "StationB", cls.branch_b)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def bind_volunteer(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Check-In",))
		make_person(first_name, "Volunteer", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_pickup_code_finds_only_the_check_ins_of_the_volunteers_church(self):
		service = make_function(
			"_Test Station A Service", church=self.branch_a, start_date=frappe.utils.today()
		)
		child = make_person("Cora", "_Test Station Child", church=self.branch_a).name
		check_in_with_code(service.name, child, "Q2RS")

		frappe.set_user(self.volunteer_b)
		self.assertEqual(get_pickup_families("Q2RS"), [])

		frappe.set_user(self.volunteer_a)
		self.assertEqual([row.person for row in get_pickup_families("Q2RS")[0]["children"]], [child])

	def test_a_joint_service_pickup_shows_a_child_of_another_church(self):
		"""With a private directory the station still finds who walks in at a shared function."""
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		joint = make_function("_Test Station Joint Pickup", church=self.branch_b, is_shared=1)
		child = make_person("Cleo", "_Test Station Joint Child", church=self.branch_b).name
		check_in_with_code(joint.name, child, "J7NT")

		frappe.set_user(self.volunteer_a)
		(family,) = get_pickup_families("J7NT")

		self.assertEqual(
			[(row.person, row.full_name) for row in family["children"]],
			[(child, "Cleo _Test Station Joint Child")],
		)

	def test_a_joint_service_pickup_lists_another_churchs_authorized_pickups(self):
		"""Another church's volunteer cannot list the pickups, but the station still reads them."""
		joint = make_function("_Test Station Joint Pickups", church=self.branch_b, is_shared=1)
		child = make_person("Cody", "_Test Station Pickup Child", church=self.branch_b)
		aunt = make_person("Ava", "_Test Station Pickup Aunt", church=self.branch_b).name
		family = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": "_Test Station Pickup Family",
				"members": [{"member": child.name}],
			}
		).insert(ignore_permissions=True)
		make_pickup(family.name, aunt)
		check_in_with_code(joint.name, child.name, "P1CK")

		frappe.set_user(self.volunteer_a)
		(found,) = get_pickup_families("P1CK")
		self.assertEqual(found["family"], family.name)
		self.assertEqual([pickup["person"] for pickup in found["pickups"]], [aunt])

	def test_a_card_finds_only_people_a_search_may_find(self):
		"""With a private directory a card from another church opens no one, except at a joint service."""
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		joint = make_function("_Test Station Joint Service", church=self.branch_b, is_shared=1).name
		holder = make_person("Carl", "_Test Station Cardholder", church=self.branch_b).name

		frappe.set_user(self.volunteer_a)
		self.assertEqual(find_card_holder(holder), [])
		self.assertEqual(
			[member.name for group in find_card_holder(holder, joint) for member in group["members"]],
			[holder],
		)

	def test_add_visitor_refuses_another_churches_family(self):
		family_a = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Station Family A", "church": self.branch_a}
		).insert(ignore_permissions=True)

		frappe.set_user(self.volunteer_b)
		with self.assertRaises(frappe.PermissionError):
			add_visitor("Vera", "_Test Station Visitor", family=family_a.name)
		self.assertFalse(frappe.db.exists("Person", {"last_name": "_Test Station Visitor"}))
		self.assertEqual(frappe.get_doc("Family", family_a.name).members, [])

		frappe.set_user(self.volunteer_a)
		visitor = add_visitor("Vera", "_Test Station Visitor", family=family_a.name)
		self.assertEqual(visitor["family"], family_a.name)
