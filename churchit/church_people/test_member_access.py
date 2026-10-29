# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What a portal member reaches of their household: their own Person, their Children, and their Family's photo."""

import frappe
from frappe.client import set_value
from frappe.handler import execute_cmd
from frappe.utils import add_days, add_years, getdate, nowdate

from churchit.church_people.matching import is_paired
from churchit.church_people.member_access import add_household_child, refuse_member_edits_beyond_photo
from churchit.church_people.test_household import born, link_user, make_household, set_adult_age
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

PHOTO = "/files/_test_household_photo.png"


class HouseholdAccessTestCase(RollbackEachTest):
	"""Two households. In each, a father and mother (Adults), a son (Child) and a grandmother (Other Adult)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household(
			"_Test Access Household"
		)
		cls.father_user = link_user(cls.father, "_test_access_father@example.com")
		cls.son_user = link_user(cls.son, "_test_access_son@example.com")
		cls.grandmother_user = link_user(cls.grandmother, "_test_access_gran@example.com")
		cls.other_family, cls.other_father, _mother, cls.other_son, _gran = make_household(
			"_Test Access Neighbours", last_name="Jones"
		)
		cls.staff = ensure_user("_test_access_staff@example.com", "Staff", roles=("Church Staff",))


class TestPersonAccess(HouseholdAccessTestCase):
	def test_an_adult_reads_and_writes_their_children_and_no_one_else(self):
		frappe.set_user(self.father_user)

		for ptype in ("read", "write"):
			self.assertTrue(frappe.has_permission("Person", ptype, doc=self.son), ptype)
			for person in (self.mother, self.grandmother, self.other_son, self.other_father):
				self.assertFalse(frappe.has_permission("Person", ptype, doc=person), (ptype, person))

	def test_a_child_reaches_only_themselves(self):
		frappe.set_user(self.son_user)

		self.assertTrue(frappe.has_permission("Person", "write", doc=self.son))
		for ptype in ("read", "write"):
			self.assertFalse(frappe.has_permission("Person", ptype, doc=self.father), ptype)

	def test_an_other_adult_reaches_only_themselves(self):
		frappe.set_user(self.grandmother_user)

		self.assertFalse(frappe.has_permission("Person", "read", doc=self.son))
		self.assertEqual(frappe.get_list("Person", pluck="name"), [self.grandmother])

	def test_an_adult_lists_themselves_and_their_children(self):
		frappe.set_user(self.father_user)

		self.assertEqual(set(frappe.get_list("Person", pluck="name")), {self.father, self.son})

	def test_an_adult_changes_only_what_personal_details_offers_on_a_child(self):
		frappe.set_user(self.father_user)
		son = frappe.get_doc("Person", self.son)
		son.alergies = "_Test Peanuts"
		son.save()

		son.nickname = "_Test Timmy"
		with self.assertRaises(frappe.PermissionError):
			son.save()

	def test_a_child_who_grows_up_leaves_the_adults_reach(self):
		frappe.db.set_value(
			"Family Members", {"parent": self.family, "member": self.son}, "household_role", "Other Adult"
		)
		frappe.set_user(self.father_user)

		self.assertFalse(frappe.has_permission("Person", "read", doc=self.son))

	def test_staff_are_untouched(self):
		frappe.set_user(self.staff)

		self.assertTrue(frappe.has_permission("Person", "read", doc=self.mother))
		self.assertIn(self.other_son, frappe.get_list("Person", pluck="name"))


class TestFamilyAccess(HouseholdAccessTestCase):
	def test_a_member_reads_only_their_own_family(self):
		for user in (self.father_user, self.son_user, self.grandmother_user):
			frappe.set_user(user)
			self.assertTrue(frappe.has_permission("Family", "read", doc=self.family), user)
			self.assertFalse(frappe.has_permission("Family", "read", doc=self.other_family), user)
			self.assertEqual(frappe.get_list("Family", pluck="name"), [self.family], user)

	def test_only_an_adult_writes_the_family(self):
		frappe.set_user(self.father_user)
		self.assertTrue(frappe.has_permission("Family", "write", doc=self.family))
		self.assertFalse(frappe.has_permission("Family", "write", doc=self.other_family))

		for user in (self.son_user, self.grandmother_user):
			frappe.set_user(user)
			self.assertFalse(frappe.has_permission("Family", "write", doc=self.family), user)

	def test_a_member_without_a_family_reaches_none(self):
		user = ensure_user("_test_access_single@example.com", "Single")
		make_person("_Test Access", "Single", user=user)
		frappe.set_user(user)

		self.assertEqual(frappe.get_list("Family", pluck="name"), [])
		self.assertFalse(frappe.has_permission("Family", "read", doc=self.family))

	def test_staff_are_untouched(self):
		frappe.set_user(self.staff)

		self.assertTrue({self.family, self.other_family} <= set(frappe.get_list("Family", pluck="name")))

	def test_an_adult_changes_the_family_photo(self):
		frappe.set_user(self.father_user)

		set_value("Family", self.family, "photo", PHOTO)

		self.assertEqual(frappe.db.get_value("Family", self.family, "photo"), PHOTO)

	def test_a_child_cannot_change_the_family_photo(self):
		frappe.set_user(self.son_user)

		with self.assertRaises(frappe.PermissionError):
			set_value("Family", self.family, "photo", PHOTO)

	def test_an_adult_changes_nothing_but_the_photo(self):
		frappe.set_user(self.father_user)

		for fieldname, value in (("family_name", "_Test Renamed"), ("primary_contact", self.mother)):
			with self.assertRaises(frappe.PermissionError, msg=fieldname):
				set_value("Family", self.family, fieldname, value)
		self.assertEqual(frappe.db.get_value("Family", self.family, "family_name"), "_Test Access Household")

	def test_the_photo_guard_names_what_a_member_may_not_change(self):
		frappe.set_user(self.father_user)
		family = frappe.get_doc("Family", self.family)
		family.load_doc_before_save()
		family.photo = PHOTO
		refuse_member_edits_beyond_photo(family)

		family.members[0].household_role = "Child"
		with self.assertRaisesRegex(frappe.PermissionError, "Family Members"):
			refuse_member_edits_beyond_photo(family)

	def test_the_apps_own_family_saves_pass_the_photo_guard(self):
		"""Saving a Person saves their family's roster, for a member too."""
		frappe.set_user(self.father_user)
		father = frappe.get_doc("Person", self.father)
		father.alergies = "_Test Pollen"
		father.save()

		self.assertEqual(frappe.db.get_value("Person", self.father, "alergies"), "_Test Pollen")


class TestAddHouseholdChild(HouseholdAccessTestCase):
	def add_child(self, user, first_name="_Test Ruth", years_old=5, gender="Female"):
		frappe.set_user(user)
		return add_household_child(first_name, "Smith", add_years(nowdate(), -years_old), gender)

	def roster_row(self, person):
		return frappe.db.get_value(
			"Family Members",
			{"parent": self.family, "member": person},
			["household_role", "relationship_to_primary_contact"],
			as_dict=True,
		)

	def test_an_adult_adds_a_child_to_their_household(self):
		child = frappe.get_doc("Person", self.add_child(self.father_user))

		self.assertEqual((child.family, child.church), (self.family, self.family_church()))
		self.assertEqual((child.membership, child.source), ("Visitor", "Portal"))
		self.assertEqual(child.birth_date, frappe.utils.getdate(add_years(nowdate(), -5)))
		self.assertFalse(any(child.get(field) for field in ("share_email", "share_phone", "share_address")))
		self.assertEqual(
			self.roster_row(child.name),
			{"household_role": "Child", "relationship_to_primary_contact": "Daughter"},
		)
		self.assertTrue(frappe.has_permission("Person", "write", doc=child.name))

	def test_a_boy_is_the_primary_contacts_son(self):
		child = self.add_child(self.father_user, "_Test Seth", gender="Male")

		self.assertEqual(self.roster_row(child).relationship_to_primary_contact, "Son")

	def test_a_child_or_an_other_adult_cannot_add_a_child(self):
		for user in (self.son_user, self.grandmother_user):
			with self.assertRaises(frappe.PermissionError, msg=user):
				self.add_child(user)

	def test_a_member_with_no_person_cannot_add_a_child(self):
		with self.assertRaises(frappe.PermissionError):
			self.add_child(ensure_user("_test_access_nobody@example.com", "Nobody"))

	def test_a_birthday_at_the_adult_age_or_in_the_future_is_refused(self):
		before = frappe.db.count("Person")
		with self.assertRaisesRegex(frappe.ValidationError, "under 18"):
			self.add_child(self.father_user, years_old=18)
		with self.assertRaisesRegex(frappe.ValidationError, "future"):
			add_household_child("_Test Ruth", "Smith", add_days(nowdate(), 1), "Female")

		self.assertEqual(frappe.db.count("Person"), before)

	def test_the_child_keeps_the_birthday_the_age_check_read(self):
		"""The database reads 05-01-10 as 2005-01-10, so a child of 16 by the check would be stored as 21."""
		birthday = getdate(add_years(nowdate(), -5))
		frappe.set_user(self.father_user)

		child = add_household_child("_Test Ruth", "Smith", birthday.strftime("%m-%d-%y"), "Female")

		self.assertEqual(frappe.db.get_value("Person", child, "birth_date"), birthday)

	def test_a_get_is_refused(self):
		"""A GET carries no CSRF token, so another site could add children from a member's browser."""
		frappe.set_user(self.father_user)
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(
			first_name="_Test Ruth", last_name="Smith", birthday=add_years(nowdate(), -5), gender="Female"
		)

		with self.assertRaises(frappe.PermissionError):
			execute_cmd("churchit.church_people.member_access.add_household_child")

	def test_a_likely_match_opens_a_possible_duplicate(self):
		known = make_person("_Test Ruth", "Smith", gender="Female", life_events=[born(5)]).name

		child = self.add_child(self.father_user)

		self.assertTrue(is_paired(child, known))

	def test_the_child_joins_the_households_church_and_is_matched_only_there(self):
		_root, branch_a, branch_b = make_two_churches()
		for person in (self.father, self.mother, self.son, self.grandmother):
			frappe.db.set_value("Person", person, "church", branch_a)
		frappe.db.set_value("Family", self.family, "church", branch_a)
		in_a = make_person("_Test Ruth", "Smith", church=branch_a, life_events=[born(5)]).name
		in_b = make_person("_Test Ruth", "Smith", church=branch_b, life_events=[born(5)]).name

		child = self.add_child(self.father_user)

		self.assertEqual(frappe.db.get_value("Person", child, "church"), branch_a)
		self.assertTrue(is_paired(child, in_a))
		self.assertFalse(is_paired(child, in_b))

	def family_church(self):
		return frappe.db.get_value("Family", self.family, "church")
