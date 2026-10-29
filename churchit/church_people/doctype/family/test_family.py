# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.permissions import add_user_permission
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.household import ADULT, CHILD, OTHER_ADULT
from churchit.church_people.merge import merge_families
from churchit.church_people.test_household import born, label, make_household, set_adult_age
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_person,
	make_primary_contact,
	make_two_churches,
)


class TestFamily(FrappeTestCase):
	def _make_person(self, first_name, **values):
		return frappe.get_doc({"doctype": "Person", "first_name": first_name, **values}).insert(
			ignore_permissions=True
		)

	def _labels(self, family_name):
		return {
			member.member: member.relationship_to_primary_contact
			for member in frappe.get_doc("Family", family_name).members
		}

	def test_primary_contact_and_spouse_are_labelled_in_members(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Labelled Household"}).insert(
			ignore_permissions=True
		)
		head = make_primary_contact(self._make_person("Head", gender="Male", family=family.name))
		wife = self._make_person("Wife", gender="Female", family=family.name)
		head.reload()
		head.spouse = wife.name
		head.marital_status = "Married"
		head.save(ignore_permissions=True)

		self.assertEqual(self._labels(family.name), {head.name: "Husband", wife.name: "Wife"})

	def test_primary_contact_must_be_a_member(self):
		outsider = self._make_person("Outsider")
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "Closed Household", "primary_contact": outsider.name}
		)

		self.assertRaises(frappe.ValidationError, family.insert, ignore_permissions=True)

	def test_adding_member_sets_person_family(self):
		person = self._make_person("Linked")
		family = frappe.get_doc({"doctype": "Family", "family_name": "Linked Household"})
		family.append("members", {"member": person.name})
		family.insert(ignore_permissions=True)

		# Family.before_save back-links the Person to this family.
		self.assertEqual(frappe.db.get_value("Person", person.name, "family"), family.name)

	def test_removing_member_clears_person_family(self):
		person = self._make_person("Unlinked")
		family = frappe.get_doc({"doctype": "Family", "family_name": "Unlinked Household"})
		family.append("members", {"member": person.name})
		family.insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Person", person.name, "family"), family.name)

		family.members = []
		family.save(ignore_permissions=True)
		self.assertIsNone(frappe.db.get_value("Person", person.name, "family"))

	def _make_household(self, family_name):
		"""A father as primary contact, his linked wife, his mother and two sons labelled on the Family."""
		family = frappe.get_doc({"doctype": "Family", "family_name": family_name}).insert(
			ignore_permissions=True
		)
		dad = make_primary_contact(self._make_person("Dad", gender="Male", family=family.name))
		mom = self._make_person(
			"Mom", gender="Female", family=family.name, marital_status="Married", spouse=dad.name
		)
		gran = self._make_person("Gran", gender="Female", family=family.name)
		bob = self._make_person("Bob", gender="Male", family=family.name)
		bill = self._make_person("Bill", gender="Male", family=family.name)
		family.reload()
		labels = {gran.name: "Mother", bob.name: "Son", bill.name: "Son"}
		for member in family.members:
			member.relationship_to_primary_contact = labels.get(
				member.member, member.relationship_to_primary_contact
			)
		family.save(ignore_permissions=True)
		return family, dad, mom, gran, bob, bill

	def test_changing_primary_contact_relates_members_to_them_and_renames_the_family(self):
		family, dad, mom, gran, bob, bill = self._make_household("Doe - Dad")
		family.reload()
		family.primary_contact = mom.name
		frappe.local.message_log = []
		family.save(ignore_permissions=True)

		self.assertEqual(
			self._labels(family.name),
			{
				dad.name: "Husband",
				mom.name: "Wife",
				gran.name: "Mother-in-law",
				bob.name: "Son",
				bill.name: "Son",
			},
		)
		self.assertEqual(family.family_name, "Doe - Mom")
		self.assertIn("Doe - Mom", str(frappe.local.message_log))

	def test_a_son_as_primary_contact_relates_his_parents_grandmother_and_brother(self):
		family, dad, mom, gran, bob, bill = self._make_household("Son - Dad")
		family.reload()
		family.primary_contact = bob.name
		family.save(ignore_permissions=True)

		self.assertEqual(
			self._labels(family.name),
			{
				dad.name: "Father",
				mom.name: "Mother",
				gran.name: "Grandmother",
				bob.name: None,
				bill.name: "Brother",
			},
		)

	def test_a_relationship_that_cannot_be_worked_out_is_cleared_and_named(self):
		family, _dad, mom, _gran, _bob, _bill = self._make_household("Cousin - Dad")
		cal = self._make_person("Cal", gender="Male", family=family.name)
		family.reload()
		for member in family.members:
			if member.member == cal.name:
				member.relationship_to_primary_contact = "Cousin"
		family.primary_contact = mom.name
		frappe.local.message_log = []
		family.save(ignore_permissions=True)

		self.assertIsNone(self._labels(family.name)[cal.name])
		self.assertIn("Set the relationship by hand for: Cal.", str(frappe.local.message_log))

	def test_sons_wife_is_labelled_as_an_in_law(self):
		family, _dad, _mom, _gran, bob, _bill = self._make_household("In-law Household")
		jane = self._make_person("Jane", gender="Female")
		bob = frappe.get_doc("Person", bob.name)
		bob.marital_status = "Married"
		bob.spouse = jane.name
		bob.save(ignore_permissions=True)

		self.assertEqual(self._labels(family.name)[jane.name], "Daughter-in-law")

	def test_married_son_starts_his_own_family_with_his_wife(self):
		family, _dad, _mom, _gran, bob, _bill = self._make_household("Parents Household")
		jane = self._make_person("Jane", gender="Female")
		bob = frappe.get_doc("Person", bob.name)
		bob.last_name = "Parents"
		bob.marital_status = "Married"
		bob.spouse = jane.name
		bob.save(ignore_permissions=True)

		bob.new_family_from_person()

		self.assertNotEqual(bob.family, family.name)
		self.assertEqual(frappe.db.get_value("Family", bob.family, "primary_contact"), bob.name)
		self.assertEqual(self._labels(bob.family), {bob.name: "Husband", jane.name: "Wife"})
		self.assertNotIn(bob.name, self._labels(family.name))
		self.assertNotIn(jane.name, self._labels(family.name))
		self.assertEqual(frappe.db.get_value("Person", jane.name, "family"), bob.family)


class TestHouseholdRoles(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def setUp(self):
		super().setUp()
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Roles"}).insert(
			ignore_permissions=True
		)
		self.family = family.name
		self.father = make_primary_contact(make_person("Father", gender="Male", family=family.name)).name
		self.mother = make_person(
			"Mother", gender="Female", family=family.name, marital_status="Married", spouse=self.father
		).name
		self.boy = make_person("Boy", family=family.name, life_events=[born(10)]).name
		self.grown_son = make_person("Grown", family=family.name, life_events=[born(25)]).name
		self.nephew = make_person("Nephew", family=family.name, life_events=[born(8)]).name
		self.lodger = make_person("Lodger", family=family.name).name
		label(self.family, {self.boy: "Son", self.grown_son: "Son", self.nephew: "Nephew"})

	def roles(self):
		return {
			member.member: member.household_role for member in frappe.get_doc("Family", self.family).members
		}

	def set_role(self, person, role):
		family = frappe.get_doc("Family", self.family)
		for member in family.members:
			if member.member == person:
				member.household_role = role
		family.save(ignore_permissions=True)

	def test_a_blank_role_is_filled_from_the_relationship_and_age(self):
		self.assertEqual(
			self.roles(),
			{
				self.father: ADULT,
				self.mother: ADULT,
				self.boy: CHILD,
				self.grown_son: OTHER_ADULT,
				self.nephew: None,
				self.lodger: None,
			},
		)

	def test_a_role_someone_set_is_kept(self):
		self.set_role(self.boy, OTHER_ADULT)
		self.set_role(self.lodger, OTHER_ADULT)
		label(self.family, {self.boy: "Grandson"})

		self.assertEqual(self.roles()[self.boy], OTHER_ADULT)
		self.assertEqual(self.roles()[self.lodger], OTHER_ADULT)

	def test_a_changed_role_sets_the_life_stage(self):
		self.assertEqual(frappe.db.get_value("Person", self.boy, "life_stage"), CHILD)

		self.set_role(self.boy, ADULT)
		self.assertEqual(frappe.db.get_value("Person", self.boy, "life_stage"), ADULT)

		self.set_role(self.lodger, OTHER_ADULT)
		self.assertEqual(frappe.db.get_value("Person", self.lodger, "life_stage"), ADULT)

	def test_a_cleared_role_is_filled_again(self):
		self.set_role(self.boy, ADULT)
		self.set_role(self.boy, None)

		self.assertEqual(self.roles()[self.boy], CHILD)
		self.assertEqual(frappe.db.get_value("Person", self.boy, "life_stage"), CHILD)


class TestAuthorizedPickups(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def setUp(self):
		super().setUp()
		self.family, _father, self.mother, self.son, self.grandmother = make_household(
			"_Test Pickups", "Pickup"
		)
		self.neighbour = make_person("Nina", "_Test Neighbour").name

	def set_pickups(self, family, *people):
		for person in people:
			frappe.get_doc({"doctype": "Authorized Pickup", "family": family, "person": person}).insert()
		return pickups_of(family)

	def test_someone_outside_the_household_or_another_adult_at_home_may_collect(self):
		self.assertEqual(
			self.set_pickups(self.family, self.neighbour, self.grandmother),
			[self.neighbour, self.grandmother],
		)

	def test_an_adult_of_the_household_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "may always collect its children"):
			self.set_pickups(self.family, self.mother)

	def test_a_child_of_the_family_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is a child of this family"):
			self.set_pickups(self.family, self.son)

	def test_a_merge_keeps_the_pickups_of_both_families_once(self):
		aunt = make_person("Ada", "_Test Aunt").name
		copy = frappe.get_doc({"doctype": "Family", "family_name": "_Test Pickups Copy"}).insert(
			ignore_permissions=True
		)
		self.set_pickups(self.family, self.neighbour)
		self.set_pickups(copy.name, aunt, self.neighbour)

		merge_families(self.family, copy.name)

		self.assertEqual(sorted(pickups_of(self.family)), sorted([self.neighbour, aunt]))

	def test_a_person_is_listed_once_for_a_family(self):
		self.set_pickups(self.family, self.neighbour)
		with self.assertRaisesRegex(frappe.ValidationError, "may already collect"):
			self.set_pickups(self.family, self.neighbour)

	def test_the_pickups_follow_the_family(self):
		self.set_pickups(self.family, self.neighbour)
		church = frappe.db.get_value("Family", self.family, "church")
		self.assertEqual(frappe.db.get_value("Authorized Pickup", {"family": self.family}, "church"), church)

		frappe.delete_doc("Family", self.family, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Authorized Pickup", {"family": self.family}))


class TestFamilyAcrossChurches(RollbackEachTest):
	"""A family takes its primary contact's church, so only that church makes someone the primary contact."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.editor_a = ensure_user(
			"_test_family_editor_a@example.com", "Editor A", roles=("Church Staff", "Church People Editor")
		)
		set_user_church(cls.editor_a, cls.branch_a)

	def test_another_churchs_person_is_not_made_the_primary_contact(self):
		"""Frappe checks the family before it takes the contact's church, so the family moved to theirs."""
		mine = make_person("_Test Across", "Mine", church=self.branch_a).name
		theirs = make_person("_Test Across", "Theirs", church=self.branch_b).name
		household = make_household_of(mine, theirs, primary_contact=mine)
		new = frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": "_Test Across New",
				"members": [{"member": theirs}],
				"primary_contact": theirs,
			}
		)

		frappe.set_user(self.editor_a)
		try:
			with self.assertRaises(frappe.PermissionError):
				new.insert()
			family = frappe.get_doc("Family", household)
			family.primary_contact = theirs
			with self.assertRaises(frappe.PermissionError):
				family.save()
		finally:
			frappe.set_user("Administrator")

		self.assertFalse(frappe.db.exists("Family", {"family_name": "_Test Across New"}))
		self.assertEqual(
			frappe.db.get_value("Family", household, ["primary_contact", "church"]), (mine, self.branch_a)
		)

	def test_another_churchs_person_cannot_be_added(self):
		mine = make_person("_Test Across", "Head", church=self.branch_a).name
		theirs = make_person("_Test Across", "Newcomer", church=self.branch_b).name
		household = make_household_of(mine, primary_contact=mine)

		frappe.set_user(self.editor_a)
		try:
			family = frappe.get_doc("Family", household)
			family.append("members", {"member": theirs})
			with self.assertRaises(frappe.PermissionError):
				family.save()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual([row.member for row in frappe.get_doc("Family", household).members], [mine])
		self.assertIsNone(frappe.db.get_value("Person", theirs, "family"))

		both = self.user("_test_family_both@example.com", "Church People Editor", self.branch_a)
		add_user_permission("Church", self.branch_b, both, ignore_permissions=True, hide_descendants=1)
		frappe.set_user(both)
		try:
			family = frappe.get_doc("Family", household)
			family.append("members", {"member": theirs})
			family.save()
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Person", theirs, "family"), household)

	def user(self, email, role, church):
		ensure_user(email, email.split("@")[0], roles=(role,))
		set_user_church(email, church)
		return email


def make_household_of(*people, **values):
	return (
		frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": "_Test Across Household",
				"members": [{"member": person} for person in people],
				**values,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def pickups_of(family):
	return frappe.get_all(
		"Authorized Pickup", filters={"family": family}, pluck="person", order_by="creation"
	)
