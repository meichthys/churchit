# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.permissions import get_doc_permissions
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_include_branches
from churchit.church_ministries.page.check_in import check_in as check_in_station
from churchit.church_people.dashboard_chart_source.people_added import people_added
from churchit.dashboard import count_families, count_people
from churchit.tests.helpers import (
	assert_scoped,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_person,
	set_multi_church,
	set_private_people,
)


class TestPeopleDirectory(FrappeTestCase):
	"""Every church reads every person and family; only their own church changes them."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		set_private_people(False)
		cls.branch_a = make_branch("_Test Directory A", "TYA")
		cls.branch_b = make_branch("_Test Directory B", "TYB")
		cls.manager_a = cls.bind_manager("_test_directory_a@example.com", "DirectoryA", cls.branch_a)
		cls.manager_b = cls.bind_manager("_test_directory_b@example.com", "DirectoryB", cls.branch_b)
		cls.parent_manager = cls.bind_manager("_test_directory_parent@example.com", "DirectoryP", cls.root)
		cls.person_a = make_person("_Test Directory", "Alpha", church=cls.branch_a).name
		cls.person_b = make_person("_Test Directory", "Bravo", church=cls.branch_b).name
		cls.family_a = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Directory Family", "church": cls.branch_a}
		).insert(ignore_permissions=True)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def bind_manager(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Manager",))
		make_person(first_name, "Manager", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_every_church_reads_another_churchs_people_and_families(self):
		frappe.set_user(self.manager_b)
		self.assertIn(self.person_a, frappe.get_list("Person", pluck="name"))
		self.assertIn(self.family_a.name, frappe.get_list("Family", pluck="name"))
		self.assertTrue(frappe.has_permission("Person", "read", doc=self.person_a))
		self.assertTrue(frappe.has_permission("Family", "read", doc=self.family_a.name))

	def test_the_desk_form_still_loads_another_churchs_person(self):
		"""A form load asks for every right at once; refusing it would take reading away too."""
		frappe.set_user(self.manager_b)
		permissions = get_doc_permissions(frappe.get_doc("Person", self.person_a))
		self.assertTrue(permissions.get("read"))

	def test_only_a_persons_own_church_may_change_them(self):
		frappe.set_user(self.manager_b)
		self.assertFalse(frappe.has_permission("Person", "write", doc=self.person_a))
		self.assertFalse(frappe.has_permission("Family", "write", doc=self.family_a.name))
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc("Person", self.person_a)

		frappe.set_user(self.manager_a)
		person = frappe.get_doc("Person", self.person_a)
		person.alergies = "_Test Directory Edit"
		person.save()

	def test_a_person_can_join_another_churchs_family(self):
		"""The roster follows the person, so editing the person is the right that counts."""
		frappe.set_user(self.manager_b)
		person = frappe.get_doc("Person", self.person_b)
		person.family = self.family_a.name
		person.save()
		frappe.set_user("Administrator")

		members = [row.member for row in frappe.get_doc("Family", self.family_a.name).members]
		self.assertIn(self.person_b, members)

	def test_editing_the_church_field_cannot_take_a_person_over(self):
		frappe.set_user(self.manager_b)
		person = frappe.get_doc("Person", self.person_a)
		person.church = self.branch_b
		with self.assertRaises(frappe.PermissionError):
			person.save()
		self.assertEqual(frappe.db.get_value("Person", self.person_a, "church"), self.branch_a)

	def test_a_new_person_cannot_be_placed_in_another_church(self):
		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Person",
					"first_name": "_Test Directory",
					"last_name": "Planted",
					"church": self.branch_a,
				}
			).insert()

	def test_a_parent_church_changes_branch_people_only_with_branches_included(self):
		frappe.set_user(self.parent_manager)
		self.assertTrue(frappe.has_permission("Person", "read", doc=self.person_a))
		self.assertFalse(frappe.has_permission("Person", "write", doc=self.person_a))

		set_include_branches(True)
		self.assertTrue(frappe.has_permission("Person", "write", doc=self.person_a))
		set_include_branches(False)

	def test_the_check_in_station_finds_every_churchs_people(self):
		frappe.set_user(self.manager_b)
		found = [
			member.name
			for group in check_in_station.search_people("_Test Directory")
			for member in group["members"]
		]
		self.assertIn(self.person_a, found)
		self.assertIn(self.person_b, found)

	def test_directory_cards_and_chart_count_only_the_readers_churches(self):
		"""Frappe's own counts would total every church now that the directory is open."""
		frappe.set_user(self.manager_b)
		mine = frappe.get_all("Person", filters={"church": self.branch_b}, pluck="name")
		self.assertEqual(count_people()["value"], len(mine))
		families = frappe.get_all("Family", filters={"church": self.branch_b}, pluck="name")
		self.assertEqual(count_families()["value"], len(families))

		name_filter = [["Person", "first_name", "=", "_Test Directory", False]]
		self.assertEqual(count_people(name_filter)["value"], 1)

		chart = people_added.get(timespan="Last Month", time_interval="Monthly")
		self.assertEqual(sum(chart["datasets"][0]["values"]), len(mine))

	def test_a_private_directory_is_scoped_like_every_other_record(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		assert_scoped(self, "Person", self.manager_b, self.person_b, self.person_a)
		frappe.set_user(self.manager_b)
		self.assertNotIn(self.family_a.name, frappe.get_list("Family", pluck="name"))
