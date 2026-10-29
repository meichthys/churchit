# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member's /household page: their own Family and its living members, and the Edit links they may follow."""

import frappe
from frappe.utils import get_html_for_route

from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.patches.v1_0 import add_household_and_directory_menu_items as menu_patch
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_address, make_person
from churchit.www.household import get_context


def page_context():
	context = frappe._dict()
	get_context(context)
	return context


class TestHouseholdPage(RollbackEachTest):
	"""The Smiths: John and Jane (Adults), Tim (Child, 10) and Gran (Other Adult). The Joneses live next door."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household("Smith - John")
		cls.father_user = link_user(cls.father, "_test_page_household_father@example.com")
		cls.son_user = link_user(cls.son, "_test_page_household_son@example.com")
		cls.other_family, cls.other_father, *_rest = make_household("Jones - John", last_name="Jones")
		address = make_address("_Test Household Home", address_line1="230 Walnut Street")
		family = frappe.get_doc("Family", cls.family)
		family.append("addresses", {"address": address.name, "is_mailing_address": 1})
		family.save(ignore_permissions=True)

	def serve(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		return get_html_for_route("household")

	def members(self):
		return {member.name: member for member in page_context().members}

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			page_context()
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/household")

	def test_a_member_sees_their_family_and_its_mailing_address(self):
		frappe.set_user(self.son_user)

		context = page_context()

		self.assertEqual(context.family.name, self.family)
		self.assertEqual(context.family_title, "The Smith Family")
		self.assertEqual(context.address, "230 Walnut Street, Springfield")

	def test_the_members_come_with_their_roles_primary_contact_first(self):
		frappe.set_user(self.son_user)

		members = page_context().members

		self.assertEqual(
			[(member.name, member.household_role) for member in members],
			[
				(self.father, "Adult"),
				(self.mother, "Adult"),
				(self.son, "Child"),
				(self.grandmother, "Other Adult"),
			],
		)
		self.assertEqual(members[0].display_name, "John Smith")

	def test_only_a_childs_known_age_shows(self):
		frappe.set_user(self.son_user)

		ages = {name: member.age for name, member in self.members().items()}

		self.assertEqual(ages, {self.father: None, self.mother: None, self.son: 10, self.grandmother: None})

	def test_someone_who_has_died_is_not_listed(self):
		frappe.db.set_value("Person", self.grandmother, "is_deceased", 1)
		frappe.set_user(self.son_user)

		self.assertNotIn(self.grandmother, self.members())

	def test_an_adult_edits_themselves_and_their_children_and_changes_the_photo(self):
		frappe.set_user(self.father_user)

		context = page_context()

		self.assertEqual(
			{member.name for member in context.members if member.can_edit}, {self.father, self.son}
		)
		self.assertTrue(context.can_change_photo)

	def test_a_child_edits_only_themselves_and_not_the_photo(self):
		frappe.set_user(self.son_user)

		context = page_context()

		self.assertEqual([member.name for member in context.members if member.can_edit], [self.son])
		self.assertFalse(context.can_change_photo)

	def test_another_household_never_shows(self):
		frappe.set_user(self.father_user)

		self.assertNotIn(self.other_father, self.members())
		self.assertNotIn("Jones", self.serve())

	def test_a_member_without_a_family_sees_only_themselves(self):
		user = ensure_user("_test_page_household_single@example.com", "Single")
		person = make_person("_Test Household", "Single", user=user).name
		frappe.set_user(user)

		context = page_context()

		self.assertIsNone(context.family)
		self.assertEqual([member.name for member in context.members], [person])
		self.assertIn("To add or remove someone, contact the church office.", self.serve())

	def test_an_account_with_no_person_sees_a_note(self):
		frappe.set_user(ensure_user("_test_page_household_nobody@example.com", "Nobody"))

		self.assertIsNone(page_context().person)
		self.assertIn("not linked to a member record", self.serve())

	def test_the_page_marks_the_member_and_links_to_personal_details(self):
		frappe.set_user(self.father_user)

		html = self.serve()

		self.assertIn("(you)", html)
		self.assertIn("age 10", html)
		self.assertIn(f'href="/personal-details/{self.son}/edit"', html)
		self.assertNotIn(f'href="/personal-details/{self.mother}/edit"', html)
		self.assertIn('id="change-household-photo"', html)

	def test_only_an_adult_gets_the_add_a_child_form(self):
		frappe.set_user(self.father_user)

		self.assertEqual(page_context().add_child.last_name, "Smith")
		self.assertIn('id="add-child"', self.serve())

		frappe.set_user(self.son_user)
		self.assertIsNone(page_context().add_child)
		self.assertNotIn('id="add-child"', self.serve())


class TestPortalMenuPatch(RollbackEachTest):
	def test_my_household_and_the_member_directory_are_added_once(self):
		frappe.db.delete(
			"Portal Menu Item", {"parent": "Portal Settings", "route": ("in", ("household", "directory"))}
		)
		frappe.db.set_single_value("People Settings", "member_directory", 0)

		menu_patch.execute()
		menu_patch.execute()

		rows = {
			row.route: row
			for row in frappe.get_single("Portal Settings").menu
			if row.route in ("household", "directory")
		}
		self.assertEqual(
			{route: (row.title, row.role, row.enabled) for route, row in rows.items()},
			{
				"household": ("My Household", "Church User", 1),
				"directory": ("Member Directory", "Church User", 0),
			},
		)
