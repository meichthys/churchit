# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_years, nowdate


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestPerson(FrappeTestCase):
	def _make_person(self, **values):
		return frappe.get_doc({"doctype": "Person", **values}).insert(ignore_permissions=True)

	def test_full_name_built_from_first_and_last(self):
		person = self._make_person(first_name="John", last_name="Doe")
		self.assertEqual(person.full_name, "John Doe")

	def test_full_name_with_only_first_name(self):
		person = self._make_person(first_name="Madonna")
		self.assertEqual(person.full_name, "Madonna")

	def test_age_computed_from_birth_life_event(self):
		_ensure("Life Event Type", {"type": "Birth"}, {"type": "Birth"})
		person = frappe.get_doc({"doctype": "Person", "first_name": "Aged"})
		person.append("life_events", {"event_type": "Birth", "date": add_years(nowdate(), -30)})
		person.insert(ignore_permissions=True)
		self.assertEqual(person.age, 30)

	def test_age_cleared_without_birth_event(self):
		person = self._make_person(first_name="Ageless")
		self.assertIsNone(person.age)

	def test_setting_family_adds_person_to_family_members(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "Smith Household"}
		).insert(ignore_permissions=True)
		person = self._make_person(first_name="Sam", last_name="Smith", family=family.name)

		family.reload()
		members = [m.member for m in family.members]
		self.assertIn(person.name, members)

	def test_removing_family_clears_head_of_household(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "Head Household"}
		).insert(ignore_permissions=True)
		person = self._make_person(
			first_name="Head", last_name="Honcho", family=family.name, is_head_of_household=1
		)
		self.assertTrue(person.is_head_of_household)

		person.family = None
		person.save(ignore_permissions=True)
		self.assertFalse(person.is_head_of_household)

	def test_deleting_person_removes_them_from_family(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "Departing Household"}
		).insert(ignore_permissions=True)
		person = self._make_person(first_name="Gone", last_name="Soon", family=family.name)
		family.reload()
		self.assertIn(person.name, [m.member for m in family.members])

		person.delete()

		family.reload()
		self.assertNotIn(person.name, [m.member for m in family.members])

	def test_spouse_link_is_reciprocated(self):
		wife = self._make_person(first_name="Jane", last_name="Doe")
		husband = self._make_person(first_name="John", last_name="Doe")

		husband.spouse = wife.name
		husband.is_married = 1
		husband.save(ignore_permissions=True)

		# The controller links the relationship back on the spouse record.
		self.assertEqual(frappe.db.get_value("Person", wife.name, "spouse"), husband.name)
		self.assertTrue(frappe.db.get_value("Person", wife.name, "is_married"))
