# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.merge import merge_people
from churchit.church_people.privacy import anonymize
from churchit.connections import get_open_count
from churchit.tests.helpers import (
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
	set_private_people,
)


def relate(person, relation_type, other):
	"""Save *person* as the session user, with a relationship of *relation_type* to *other*."""
	doc = frappe.get_doc("Person", person.name)
	doc.append("relationships", {"relation_type": relation_type, "person": other.name})
	doc.save()


def relationships_of(person):
	return [(row.relation_type, row.person) for row in frappe.get_doc("Person", person.name).relationships]


class TestRelationships(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		set_private_people(False)
		cls.addClassCleanup(frappe.clear_cache)
		cls.grandfather = ensure("Person Relation Type", {"type": "Grandfather"})
		cls.uncle = ensure("Person Relation Type", {"type": "Uncle"})
		cls.manager_a = ensure_user(
			"_test_relationships_a@example.com", "RelationshipsA", roles=("Church Manager",)
		)
		make_person("_Test Relationships", "Manager", church=cls.branch_a, user=cls.manager_a)

	def tearDown(self):
		frappe.set_user("Administrator")
		# Frappe's get_open_count limits the session's statements to 1 second, meant to end with the request.
		frappe.db.set_execution_timeout(0)

	def make_family(self, family_name, *people):
		frappe.get_doc(
			{
				"doctype": "Family",
				"family_name": family_name,
				"church": people[0].church,
				"members": [{"member": person.name} for person in people],
			}
		).insert(ignore_permissions=True)

	def test_a_grandparent_in_another_household_sees_the_child_in_their_connections(self):
		child = make_person("_Test Grandchild", "Connected", church=self.branch_a)
		grandparent = make_person("_Test Grandparent", "Connected", church=self.branch_a)
		self.make_family("_Test Child Household", child)
		self.make_family("_Test Grandparent Household", grandparent)
		frappe.set_user(self.manager_a)
		relate(child, self.grandfather, grandparent)

		found = get_open_count("Person", grandparent.name, ["Person"])["count"]["external_links_found"]

		self.assertEqual({row["doctype"]: row["count"] for row in found}, {"Person": 1})
		self.assertFalse(frappe.get_doc("Person", grandparent.name).relationships)

	def test_a_relation_type_counts_the_people_who_record_it(self):
		child = make_person("_Test Relationships", "Counted", church=self.branch_a)
		grandparent = make_person("_Test Relationships", "Counted Grandparent", church=self.branch_a)
		relate(child, self.grandfather, grandparent)
		frappe.set_user(self.manager_a)

		found = get_open_count("Person Relation Type", self.grandfather)["count"]["external_links_found"]

		self.assertEqual(found[0]["doctype"], "Person")
		self.assertGreaterEqual(found[0]["count"], 1)

	def test_a_person_cannot_have_a_relationship_with_themselves(self):
		person = make_person("_Test Relationships", "Self", church=self.branch_a)

		with self.assertRaisesRegex(frappe.ValidationError, "themselves"):
			relate(person, self.uncle, person)

	def test_the_same_relationship_twice_is_refused(self):
		child = make_person("_Test Relationships", "Twice", church=self.branch_a)
		grandparent = make_person("_Test Relationships", "Once", church=self.branch_a)
		relate(child, self.grandfather, grandparent)

		with self.assertRaisesRegex(frappe.ValidationError, "already in the table"):
			relate(child, self.grandfather, grandparent)
		relate(child, self.uncle, grandparent)

		self.assertEqual(
			relationships_of(child), [(self.grandfather, grandparent.name), (self.uncle, grandparent.name)]
		)

	def test_a_person_in_the_same_household_is_refused(self):
		child = make_person("_Test Relationships", "Child", church=self.branch_a)
		grandparent = make_person("_Test Relationships", "Live-in", church=self.branch_a)
		self.make_family("_Test Shared Household", child, grandparent)

		with self.assertRaisesRegex(frappe.ValidationError, "same household"):
			relate(child, self.grandfather, grandparent)

	def test_a_relationship_stays_when_the_people_move_into_one_household(self):
		child = make_person("_Test Relationships", "Mover", church=self.branch_a)
		grandparent = make_person("_Test Relationships", "Host", church=self.branch_a)
		relate(child, self.grandfather, grandparent)
		self.make_family("_Test Joined Household", child, grandparent)

		moved = frappe.get_doc("Person", child.name)
		moved.nickname = "Moved"
		moved.save()

		self.assertEqual(relationships_of(child), [(self.grandfather, grandparent.name)])

	def test_another_churchs_person_is_refused_only_in_a_private_directory(self):
		child = make_person("_Test Relationships", "Branch A", church=self.branch_a)
		uncle = make_person("_Test Relationships", "Branch B", church=self.branch_b)
		grandparent = make_person("_Test Relationships", "Branch B Grandparent", church=self.branch_b)
		frappe.set_user(self.manager_a)
		relate(child, self.uncle, uncle)
		frappe.set_user("Administrator")
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		frappe.set_user(self.manager_a)

		kept = frappe.get_doc("Person", child.name)
		kept.nickname = "Kept"
		kept.save()
		with self.assertRaisesRegex(frappe.PermissionError, "another church"):
			relate(child, self.grandfather, grandparent)

	def test_a_private_directory_hides_another_churchs_relationship_from_connections(self):
		child = make_person("_Test Relationships", "Hidden Grandchild", church=self.branch_b)
		grandparent = make_person("_Test Relationships", "Seen Grandparent", church=self.branch_a)
		relate(child, self.grandfather, grandparent)
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		frappe.set_user(self.manager_a)

		found = get_open_count("Person", grandparent.name, ["Person"])["count"]["external_links_found"]

		self.assertEqual({row["doctype"]: row["count"] for row in found}, {"Person": 0})
		self.assertFalse(frappe.get_list("Person", filters={"person": grandparent.name}))

	def test_a_merge_keeps_the_rows_and_drops_one_naming_the_kept_person(self):
		grandparent = make_person("_Test Relationships", "Grandparent")
		uncle = make_person("_Test Relationships", "Uncle")
		kept = make_person("_Test Relationships", "Kept")
		removed = make_person("_Test Relationships", "Removed")
		relate(kept, self.grandfather, grandparent)
		relate(kept, self.uncle, removed)
		relate(removed, self.grandfather, grandparent)
		relate(removed, self.uncle, uncle)

		merge_people(kept.name, removed.name)

		self.assertEqual(
			relationships_of(kept), [(self.grandfather, grandparent.name), (self.uncle, uncle.name)]
		)

	def test_a_merge_leaves_another_person_one_row_for_the_kept_person(self):
		child = make_person("_Test Relationships", "Grandchild")
		kept = make_person("_Test Relationships", "Kept Grandparent")
		removed = make_person("_Test Relationships", "Removed Grandparent")
		relate(child, self.grandfather, kept)
		relate(child, self.grandfather, removed)
		relate(child, self.uncle, removed)

		merge_people(kept.name, removed.name)

		self.assertEqual(relationships_of(child), [(self.grandfather, kept.name), (self.uncle, kept.name)])

	def test_anonymizing_removes_every_row_that_names_the_person(self):
		person = make_person("_Test Relationships", "Forgotten")
		grandparent = make_person("_Test Relationships", "Their Grandparent")
		nephew = make_person("_Test Relationships", "Their Nephew")
		relate(person, self.grandfather, grandparent)
		relate(nephew, self.uncle, person)
		relate(nephew, self.grandfather, grandparent)

		anonymize(person.name)

		self.assertEqual(relationships_of(person), [])
		self.assertEqual(relationships_of(nephew), [(self.grandfather, grandparent.name)])

	def test_deleting_a_person_removes_the_relationships_naming_them(self):
		child = make_person("_Test Relationships", "Left Behind")
		grandparent = make_person("_Test Relationships", "Deleted Grandparent")
		relate(child, self.grandfather, grandparent)

		frappe.delete_doc("Person", grandparent.name)

		self.assertEqual(relationships_of(child), [])
