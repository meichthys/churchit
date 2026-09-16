# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestFamily(FrappeTestCase):
	def _make_person(self, first_name, **values):
		return frappe.get_doc({"doctype": "Person", "first_name": first_name, **values}).insert(
			ignore_permissions=True
		)

	def test_head_of_household_spouse_is_labelled_in_members(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "Labelled Household"}).insert(
			ignore_permissions=True
		)
		head = self._make_person("Head", gender="Male", family=family.name, is_head_of_household=1)
		wife = self._make_person("Wife", gender="Female", family=family.name)
		head.spouse = wife.name
		head.is_married = 1
		head.save(ignore_permissions=True)

		labels = {m.member: m.relationship_to_head for m in frappe.get_doc("Family", family.name).members}
		self.assertEqual(labels, {head.name: None, wife.name: "Wife"})

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
