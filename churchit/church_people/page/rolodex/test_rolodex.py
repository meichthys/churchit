# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.page.rolodex.rolodex import get_directory, save_settings
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_address,
	make_person,
	make_two_churches,
	set_private_people,
)


def card_for(directory, name):
	return next(person for person in directory["people"] if person.name == name)


class TestRolodexCards(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Life Event Type", {"type": "Birth"})
		cls.elder = ensure("Position Type", {"position": "_Test Rolodex Elder"})
		usher = ensure("Position Type", {"position": "_Test Rolodex Usher"})
		cls.family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Rolodex - Household"})
		cls.family.append("phones", {"phone_number": "202-555-0190"})
		cls.family.insert(ignore_permissions=True)
		address = make_address(
			"_Test Rolodex Home", address_line1="12 Elm St", state="IL", pincode="62701"
		).name
		person = frappe.get_doc(
			{
				"doctype": "Person",
				"first_name": "_Test Rolodex",
				"last_name": "Card",
				"family": cls.family.name,
			}
		)
		person.append("emails", {"email_address": "_test_rolodex_card@example.com"})
		person.append("phones", {"phone_number": "202-555-0191"})
		person.append("addresses", {"address": address})
		person.append("life_events", {"event_type": "Birth", "date": "1980-03-14"})
		person.append("positions", {"position": cls.elder, "start_date": "2020-01-01"})
		person.append("positions", {"position": usher, "start_date": "2019-01-01", "end_date": "2020-01-01"})
		cls.person = person.insert(ignore_permissions=True)
		cls.group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test Rolodex Choir",
				"members": [{"person": cls.person.name}],
			}
		).insert(ignore_permissions=True)

	def test_a_card_carries_contact_details_and_what_its_back_shows(self):
		card = card_for(get_directory(), self.person.name)

		self.assertEqual((card.phone, card.email), ("202-555-0191", "_test_rolodex_card@example.com"))
		self.assertEqual(card.address, "12 Elm St, Springfield, IL 62701")
		self.assertIn("openstreetmap.org", card.map_url)
		self.assertEqual(str(card.birthday), "1980-03-14")
		self.assertEqual(card.groups, [self.group.name])

	def test_only_positions_held_today_are_listed(self):
		self.assertEqual(card_for(get_directory(), self.person.name).positions, [self.elder])

	def test_a_household_carries_its_own_contact_details(self):
		family = next(family for family in get_directory()["families"] if family.name == self.family.name)
		self.assertEqual(family.phone, "202-555-0190")

	def test_filter_choices_list_groups_and_positions(self):
		choices = get_directory()["choices"]
		self.assertIn([self.group.name, "_Test Rolodex Choir"], choices["group"])
		self.assertIn(self.elder, choices["position"])


class TestRolodexSettings(FrappeTestCase):
	def test_saved_cards_survive_a_cache_clear(self):
		"""Frappe's own user settings wait in the cache for an hourly sync, and a clear loses them."""
		save_settings(frappe.as_json(["_Test Saved Person"]), "households", "false")
		frappe.clear_cache()

		self.assertEqual(
			get_directory()["settings"],
			{"saved": ["_Test Saved Person"], "view": "households", "filters_open": False},
		)


class TestRolodexSingleChurch(FrappeTestCase):
	def setUp(self):
		ensure_root_church()
		force_single_church()

	def test_a_single_church_site_offers_no_church_filter(self):
		self.assertEqual(get_directory()["choices"]["church"], [])


class TestRolodexBranches(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_rolodex_a@example.com", "RolodexA", roles=("Church Manager",))
		make_person("RolodexA", "Manager", church=cls.branch_a, user=cls.manager_a)
		cls.person_b = make_person("_Test Rolodex", "Branch", church=cls.branch_b).name
		cls.group_b = (
			frappe.get_doc(
				{
					"doctype": "Group",
					"group_name": "_Test Rolodex Branch Group",
					"church": cls.branch_b,
					"members": [{"person": cls.person_b}],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		cls.addClassCleanup(frappe.clear_cache)

	def tearDown(self):
		frappe.set_user("Administrator")

	def directory_for_manager_a(self):
		frappe.set_user(self.manager_a)
		return get_directory()

	def test_another_churchs_group_stays_out_of_view(self):
		"""The directory is shared, but a branch's groups are its own."""
		set_private_people(False)
		directory = self.directory_for_manager_a()

		self.assertEqual(card_for(directory, self.person_b).groups, [])
		self.assertNotIn(self.group_b, [name for name, _title in directory["choices"]["group"]])
		self.assertNotIn(self.branch_b, [name for name, _title in directory["choices"]["church"]])

	def test_a_private_directory_leaves_out_another_churchs_people(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		names = [person.name for person in self.directory_for_manager_a()["people"]]
		self.assertNotIn(self.person_b, names)
