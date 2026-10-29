# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, nowdate

from churchit.church_people.household import (
	ADULT,
	CHILD,
	OTHER_ADULT,
	can_edit,
	get_ages,
	get_editable_children,
	get_household_role,
	members,
	role_of,
	salutation,
)
from churchit.patches.v1_0 import fill_household_roles, repair_early_household_roles
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_primary_contact


def set_adult_age(age):
	settings = frappe.get_single("People Settings")
	settings.adult_age = age
	settings.save(ignore_permissions=True)


def born(years_ago):
	"""A Birth life event row for someone *years_ago* years old."""
	return {
		"event_type": ensure("Life Event Type", {"type": "Birth"}),
		"date": add_years(nowdate(), -years_ago),
	}


def make_household(family_name, last_name="Smith"):
	"""A father as primary contact, his wife, a son of 10 and the father's mother of 70, roles filled on save."""
	family = frappe.get_doc({"doctype": "Family", "family_name": family_name}).insert(ignore_permissions=True)
	father = make_primary_contact(make_person("John", last_name, gender="Male", family=family.name))
	mother = make_person(
		"Jane", last_name, gender="Female", family=family.name, marital_status="Married", spouse=father.name
	)
	son = make_person("Tim", last_name, gender="Male", family=family.name, life_events=[born(10)])
	grandmother = make_person("Gran", last_name, gender="Female", family=family.name, life_events=[born(70)])
	label(family.name, {son.name: "Son", grandmother.name: "Mother"})
	return family.name, father.name, mother.name, son.name, grandmother.name


def label(family_name, relationships):
	"""Set each member's relationship to the primary contact from *relationships* and save the family."""
	family = frappe.get_doc("Family", family_name)
	for member in family.members:
		member.relationship_to_primary_contact = relationships.get(
			member.member, member.relationship_to_primary_contact
		)
	family.save(ignore_permissions=True)


def link_user(person, email):
	user = ensure_user(email, frappe.db.get_value("Person", person, "first_name"))
	frappe.db.set_value("Person", person, "user", user)
	return user


class TestHouseholdRoleRule(FrappeTestCase):
	def test_the_primary_contact_and_their_spouse_are_adults(self):
		self.assertEqual(get_household_role(True, None, None, 18), ADULT)
		self.assertEqual(get_household_role(False, "Wife", 16, 18), ADULT)

	def test_a_child_step_child_or_grandchild_under_the_adult_age_is_a_child(self):
		for relationship in ("Son", "Stepdaughter", "Grandson"):
			self.assertEqual(get_household_role(False, relationship, 10, 18), CHILD, relationship)

	def test_anyone_else_at_the_adult_age_is_an_other_adult(self):
		for relationship in ("Son", "Grandmother", None):
			self.assertEqual(get_household_role(False, relationship, 18, 18), OTHER_ADULT, relationship)

	def test_a_member_it_cannot_place_is_left_blank(self):
		self.assertIsNone(get_household_role(False, None, None, 18))
		self.assertIsNone(get_household_role(False, "Son", None, 18))
		self.assertIsNone(get_household_role(False, "Nephew", 8, 18))


class TestHousehold(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household("_Test Household")

	def test_role_of_reads_the_roster(self):
		self.assertEqual(
			[role_of(person) for person in (self.father, self.mother, self.son, self.grandmother)],
			[ADULT, ADULT, CHILD, OTHER_ADULT],
		)
		self.assertIsNone(role_of(make_person("_Test Familyless").name))

	def test_members_who_join_before_the_primary_contact_wait_for_their_roles(self):
		"""Until someone is the primary contact, no one's relationship to them is known."""
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Members First"}).insert(
			ignore_permissions=True
		)
		father = make_person("Ray", "First", gender="Male", family=family.name, life_events=[born(40)])
		mother = make_person(
			"Rae",
			"First",
			gender="Female",
			family=family.name,
			marital_status="Married",
			spouse=father.name,
			life_events=[born(38)],
		)
		self.assertEqual([role_of(father.name), role_of(mother.name)], [None, None])

		make_primary_contact(father)

		self.assertEqual([role_of(father.name), role_of(mother.name)], [ADULT, ADULT])

	def test_an_age_is_known_from_a_birth_date_and_after_a_death_from_its_date(self):
		frappe.db.set_value("Person", self.grandmother, {"is_deceased": 1, "deceased_date": None})
		self.assertEqual(get_ages([self.father, self.son, self.grandmother]), {self.son: 10})

		frappe.db.set_value("Person", self.grandmother, "deceased_date", nowdate())
		self.assertEqual(get_ages([self.grandmother]), {self.grandmother: 70})

	def test_members_lists_the_roster_with_the_primary_contact_first(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Late Contact"}).insert(
			ignore_permissions=True
		)
		child = make_person("Kid", family=family.name)
		parent = make_primary_contact(make_person("Parent", family=family.name))

		self.assertEqual(members(family.name), [parent.name, child.name])
		self.assertEqual(members(self.family), [self.father, self.mother, self.son, self.grandmother])

	def test_members_narrows_to_the_roles_asked_for(self):
		self.assertEqual(members(self.family, [ADULT]), [self.father, self.mother])
		self.assertEqual(members(self.family, [CHILD, OTHER_ADULT]), [self.son, self.grandmother])

	def test_members_leaves_out_people_who_have_died(self):
		frappe.db.set_value("Person", self.grandmother, "is_deceased", 1)

		self.assertNotIn(self.grandmother, members(self.family))

	def test_a_user_may_edit_themselves(self):
		for person in (self.father, self.son, self.grandmother):
			user = link_user(person, f"_test_household_{person.lower()}@example.com")
			self.assertTrue(can_edit(user, person), person)

	def test_an_adult_may_edit_the_familys_children_only(self):
		user = link_user(self.father, "_test_household_father@example.com")

		self.assertTrue(can_edit(user, self.son))
		self.assertFalse(can_edit(user, self.mother))
		self.assertFalse(can_edit(user, self.grandmother))

	def test_an_other_adult_or_a_child_may_edit_no_one_else(self):
		grandmother = link_user(self.grandmother, "_test_household_gran@example.com")
		son = link_user(self.son, "_test_household_tim@example.com")

		self.assertFalse(can_edit(grandmother, self.son))
		self.assertFalse(can_edit(son, self.father))

	def test_an_adult_of_another_family_may_not_edit_this_ones_children(self):
		_family, other_father, *_rest = make_household("_Test Other Household", last_name="Jones")
		user = link_user(other_father, "_test_household_other@example.com")

		self.assertFalse(can_edit(user, self.son))

	def test_a_user_with_no_person_may_edit_nobody(self):
		user = ensure_user("_test_household_nobody@example.com", "Nobody")

		self.assertFalse(can_edit(user, self.son))
		self.assertFalse(can_edit("", self.son))

	def test_an_adults_editable_children_are_the_living_children_of_their_family(self):
		daughter = make_person("Amy", "Smith", family=self.family, life_events=[born(7)]).name
		label(self.family, {daughter: "Daughter"})
		father = link_user(self.father, "_test_household_father@example.com")

		self.assertEqual(get_editable_children(father), [self.son, daughter])

		frappe.db.set_value("Person", daughter, "is_deceased", 1)
		self.assertEqual(get_editable_children(father), [self.son])

	def test_a_child_at_the_adult_age_is_no_longer_the_adults_to_edit(self):
		"""A Child stays one on the roster until someone changes the role, so the age decides."""
		ageless = make_person("Sam", "Smith", family=self.family).name
		frappe.db.set_value(
			"Family Members", {"parent": self.family, "member": ageless}, "household_role", CHILD
		)
		father = link_user(self.father, "_test_household_father@example.com")

		frappe.db.set_single_value("People Settings", "adult_age", 11)
		self.assertEqual(get_editable_children(father), [self.son, ageless])

		frappe.db.set_single_value("People Settings", "adult_age", 10)
		self.assertEqual(get_editable_children(father), [ageless])
		self.assertFalse(can_edit(father, self.son))
		self.assertTrue(can_edit(father, ageless))

	def test_no_one_else_has_editable_children(self):
		grandmother = link_user(self.grandmother, "_test_household_gran@example.com")
		single = ensure_user("_test_household_single@example.com", "Single")
		make_person("_Test Familyless", user=single)

		for user in (grandmother, single, ensure_user("_test_household_nobody@example.com", "Nobody"), ""):
			self.assertEqual(get_editable_children(user), [], user)

	def test_salutation_names_the_adults_and_their_shared_last_name_once(self):
		self.assertEqual(salutation(self.family), "John & Jane Smith")

	def test_salutation_prefers_a_nickname(self):
		frappe.db.set_value("Person", self.mother, "nickname", "Janie")

		self.assertEqual(salutation(self.family), "John & Janie Smith")

	def test_salutation_gives_each_adult_their_own_last_name_when_they_differ(self):
		frappe.db.set_value("Person", self.mother, "last_name", "Doe")

		self.assertEqual(salutation(self.family), "John Smith & Jane Doe")

	def test_salutation_leaves_out_an_adult_who_has_died(self):
		frappe.db.set_value("Person", self.mother, "is_deceased", 1)

		self.assertEqual(salutation(self.family), "John Smith")

	def test_salutation_falls_back_to_the_family_name_without_an_adult(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Orphans - Kid"}).insert(
			ignore_permissions=True
		)
		make_person("Kid", family=family.name, life_events=[born(8)])

		self.assertEqual(salutation(family.name), "_Test Orphans - Kid")
		self.assertEqual(salutation(None), "")


class TestFillHouseholdRolesPatch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def setUp(self):
		super().setUp()
		# Settle every other family on the site, so only this test's rows are left to the patch.
		frappe.db.sql(
			"update `tabFamily Members` set household_role = 'Other Adult' where ifnull(household_role, '') = ''"
		)
		self.manager = ensure_user(
			"_test_household_manager@example.com", "Manager", roles=("Church Manager",)
		)

	def make_upgraded_household(self, family_name):
		"""A household whose roles and life stages are blank, as on a site from before household roles."""
		household = make_household(family_name)
		frappe.db.sql("update `tabFamily Members` set household_role = null where parent = %s", household[0])
		frappe.db.sql("update `tabPerson` set life_stage = null where family = %s", household[0])
		return household

	def new_todos(self, before):
		return frappe.get_all(
			"ToDo",
			filters={"name": ("not in", before or [""]), "role": "Church Manager"},
			fields=["description", "allocated_to"],
		)

	def test_fills_the_roles_and_life_stages_without_saving_the_family(self):
		family, father, mother, son, grandmother = self.make_upgraded_household("_Test Upgraded")
		modified = frappe.db.get_value("Family", family, "modified")

		fill_household_roles.execute()

		self.assertEqual(
			[role_of(person) for person in (father, mother, son, grandmother)],
			[ADULT, ADULT, CHILD, OTHER_ADULT],
		)
		self.assertEqual(frappe.db.get_value("Person", son, "life_stage"), CHILD)
		self.assertEqual(frappe.db.get_value("Family", family, "modified"), modified)

	def test_the_members_left_over_go_to_a_church_manager_in_one_todo(self):
		family, _father, _mother, son, _grandmother = self.make_upgraded_household("_Test Lodgers")
		lodger = make_person("Lodger", family=family)
		late_lodger = make_person("Late Lodger", family=family)
		frappe.db.sql("update `tabFamily Members` set household_role = null where parent = %s", family)
		frappe.db.set_value("Person", late_lodger.name, "is_deceased", 1)
		before = frappe.get_all("ToDo", pluck="name")

		fill_household_roles.execute()

		todos = self.new_todos(before)
		self.assertEqual(len(todos), 1)
		self.assertIn(lodger.name, todos[0].description)
		self.assertIn("_Test Lodgers", todos[0].description)
		self.assertNotIn(son, todos[0].description)
		self.assertNotIn(late_lodger.name, todos[0].description)
		self.assertNotEqual(todos[0].allocated_to, "Administrator")
		self.assertIn("Church Manager", frappe.get_roles(todos[0].allocated_to))

	def test_no_todo_when_every_role_is_filled(self):
		self.make_upgraded_household("_Test Settled")
		before = frappe.get_all("ToDo", pluck="name")

		fill_household_roles.execute()

		self.assertEqual(self.new_todos(before), [])

	def test_refuses_to_run_before_the_adult_age_is_set(self):
		frappe.db.set_single_value("People Settings", "adult_age", 0)

		self.assertRaises(frappe.ValidationError, fill_household_roles.execute)


class TestRepairEarlyHouseholdRolesPatch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)

	def test_the_primary_contact_and_spouse_become_adults_and_no_one_else_changes(self):
		family, father, mother, son, grandmother = make_household("_Test Filled Early")
		frappe.db.sql(
			"update `tabFamily Members` set household_role = 'Other Adult' where parent = %s and member in %s",
			(family, (father, mother)),
		)
		frappe.db.set_value("Person", father, "life_stage", "Other Adult")
		modified = frappe.db.get_value("Family", family, "modified")

		repair_early_household_roles.execute()

		self.assertEqual(
			[role_of(person) for person in (father, mother, son, grandmother)],
			[ADULT, ADULT, CHILD, OTHER_ADULT],
		)
		self.assertEqual(frappe.db.get_value("Person", father, "life_stage"), "Adult")
		self.assertEqual(frappe.db.get_value("Family", family, "modified"), modified)
