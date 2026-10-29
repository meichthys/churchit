# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.page.check_in.check_in import get_pickup_families, release_children
from churchit.church_ministries.page.check_in.test_check_in import check_in_with_code
from churchit.church_people.doctype.family.test_pickup_scope import make_pickup
from churchit.church_people.test_household import make_household, set_adult_age
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_function, make_person


class TestPickupRelease(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		cls.volunteer = ensure_user(
			"_test_release_volunteer@example.com", "ReleaseVolunteer", roles=("Church Check-In",)
		)

	def setUp(self):
		super().setUp()
		function = make_function("_Test Release Service", start_date=frappe.utils.today()).name
		self.family, self.father, _mother, self.son, self.grandmother = make_household(
			"_Test Release Household", "Releaseton"
		)
		self.daughter = make_person("Dot", "Releaseton", family=self.family).name
		self.aunt = make_person("Ada", "_Test Release Aunt").name
		make_pickup(self.family, self.aunt, relationship=ensure("Person Relation Type", {"type": "Aunt"}))
		self.son_check_in = check_in_with_code(function, self.son, "R4LS").name
		self.daughter_check_in = check_in_with_code(function, self.daughter, "R4LS").name
		frappe.set_user(self.volunteer)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_the_volunteer_records_who_collected_each_ticked_child(self):
		(family,) = release_children("r4ls", [self.son_check_in], self.father)

		collected = frappe.db.get_value(
			"Function Check-In",
			self.son_check_in,
			["collected_by", "collected_by_name", "released_by", "collected_at"],
			as_dict=True,
		)
		self.assertEqual(
			(collected.collected_by, collected.collected_by_name, collected.released_by),
			(self.father, "John Releaseton", self.volunteer),
		)
		self.assertTrue(collected.collected_at)
		by_check_in = {child.check_in: child.collected_by for child in family["children"]}
		self.assertEqual(by_check_in, {self.son_check_in: self.father, self.daughter_check_in: None})

	def test_an_authorized_pickup_may_collect_and_a_child_is_released_once(self):
		release_children("R4LS", frappe.as_json([self.daughter_check_in]), self.aunt)
		self.assertEqual(
			frappe.db.get_value("Function Check-In", self.daughter_check_in, "collected_by"), self.aunt
		)

		with self.assertRaisesRegex(frappe.ValidationError, "already been collected"):
			release_children("R4LS", [self.daughter_check_in], self.father)

	def test_no_one_else_takes_the_children(self):
		stranger = make_person("Sly", "_Test Release Stranger").name
		for collector in (stranger, self.grandmother):
			with self.subTest(collector), self.assertRaises(frappe.PermissionError):
				release_children("R4LS", [self.son_check_in], collector)
		self.assertIsNone(frappe.db.get_value("Function Check-In", self.son_check_in, "collected_by"))

	def test_only_a_child_of_this_code_is_released(self):
		with self.assertRaises(frappe.PermissionError):
			release_children("ZZZZ", [self.son_check_in], self.father)
		self.assertIsNone(frappe.db.get_value("Function Check-In", self.son_check_in, "collected_by"))

	def test_only_the_check_in_right_may_release(self):
		staff = ensure_user("_test_release_staff@example.com", "ReleaseStaff", roles=("Church Staff",))
		frappe.set_user(staff)
		with self.assertRaises(frappe.PermissionError):
			release_children("R4LS", [self.son_check_in], self.father)

	def test_the_code_shows_who_took_a_child_and_when(self):
		release_children("R4LS", [self.son_check_in], self.father)

		(family,) = get_pickup_families("R4LS")
		(son,) = [child for child in family["children"] if child.person == self.son]
		self.assertEqual((son.collected_by_name, bool(son.collected_at)), ("John Releaseton", True))

	def test_a_restricted_adult_may_not_collect_that_child(self):
		make_restriction(self.son, self.father)

		with self.assertRaisesRegex(frappe.PermissionError, "Pickup Restriction"):
			release_children("R4LS", [self.son_check_in, self.daughter_check_in], self.father)
		self.assertIsNone(frappe.db.get_value("Function Check-In", self.daughter_check_in, "collected_at"))

		release_children("R4LS", [self.daughter_check_in], self.father)
		self.assertEqual(
			frappe.db.get_value("Function Check-In", self.daughter_check_in, "collected_by"), self.father
		)

	def test_a_restriction_ends_after_its_last_day(self):
		make_restriction(self.son, self.father, valid_until=frappe.utils.add_days(frappe.utils.today(), -1))

		release_children("R4LS", [self.son_check_in], self.father)
		self.assertEqual(
			frappe.db.get_value("Function Check-In", self.son_check_in, "collected_by"), self.father
		)

	def test_the_station_sees_what_to_do_but_not_why(self):
		make_restriction(
			self.son, self.father, description="_Test Call the office", reason="_Test Court order"
		)

		(family,) = get_pickup_families("R4LS")
		(restriction,) = family["restrictions"]
		self.assertEqual(
			(restriction.child, restriction.restricted_person, restriction.description),
			(self.son, self.father, "_Test Call the office"),
		)
		self.assertNotIn("reason", restriction)
		self.assertNotIn("court_order", restriction)

	def test_only_a_church_manager_overrides_a_restriction_and_it_is_recorded(self):
		make_restriction(self.son, self.father)
		with self.assertRaises(frappe.PermissionError):
			release_children("R4LS", [self.son_check_in], self.father, override_reason="_Test Mother called")

		manager = ensure_user(
			"_test_release_manager@example.com", "ReleaseManager", roles=("Church Manager",)
		)
		frappe.set_user(manager)
		release_children("R4LS", [self.son_check_in], self.father, override_reason="  _Test Mother called ")

		collected = frappe.db.get_value(
			"Function Check-In",
			self.son_check_in,
			["collected_by", "collected_at", "released_by", "override_reason", "overridden_by"],
			as_dict=True,
		)
		self.assertTrue(collected.collected_at)
		self.assertEqual(
			(
				collected.collected_by,
				collected.released_by,
				collected.override_reason,
				collected.overridden_by,
			),
			(self.father, manager, "_Test Mother called", manager),
		)


def make_restriction(child, restricted_person, **values):
	return frappe.get_doc(
		{
			"doctype": "Pickup Restriction",
			"child": child,
			"restricted_person": restricted_person,
			"description": "_Test Ask the office",
			**values,
		}
	).insert(ignore_permissions=True)
