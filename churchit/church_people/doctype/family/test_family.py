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

	def _make_household(self, family_name):
		"""A father as head, his linked wife, and two sons labelled on the Family."""
		family = frappe.get_doc({"doctype": "Family", "family_name": family_name}).insert(
			ignore_permissions=True
		)
		head = self._make_person("Dad", gender="Male", family=family.name, is_head_of_household=1)
		mom = self._make_person("Mom", gender="Female", family=family.name, is_married=1, spouse=head.name)
		bob = self._make_person("Bob", gender="Male", family=family.name)
		bill = self._make_person("Bill", gender="Male", family=family.name)
		family.reload()
		for member in family.members:
			if member.member in (bob.name, bill.name):
				member.relationship_to_head = "Son"
		family.save(ignore_permissions=True)
		return family, head, mom, bob, bill

	def _relations(self, person):
		return {
			row.person: (row.type, row.from_family) for row in frappe.get_doc("Person", person.name).relations
		}

	def test_family_labels_fill_in_relations(self):
		_family, head, mom, bob, bill = self._make_household("Relations Household")

		self.assertEqual(
			self._relations(bob),
			{head.name: ("Father", 1), mom.name: ("Mother", 1), bill.name: ("Brother", 1)},
		)
		self.assertEqual(
			self._relations(head), {mom.name: ("Wife", 0), bob.name: ("Son", 1), bill.name: ("Son", 1)}
		)
		self.assertEqual(
			self._relations(mom), {head.name: ("Husband", 0), bob.name: ("Son", 1), bill.name: ("Son", 1)}
		)

	def test_relation_entered_by_hand_wins(self):
		_family, _head, _mom, bob, bill = self._make_household("Hand Household")
		bob = frappe.get_doc("Person", bob.name)
		bob.relations = [row for row in bob.relations if row.person != bill.name]
		bob.append("relations", {"person": bill.name, "type": "Stepbrother"})
		bob.save(ignore_permissions=True)

		self.assertEqual(self._relations(bob)[bill.name], ("Stepbrother", 0))

	def test_unticking_from_family_keeps_one_row(self):
		_family, _head, _mom, bob, bill = self._make_household("Untick Household")
		bob = frappe.get_doc("Person", bob.name)
		row = next(row for row in bob.relations if row.person == bill.name)
		row.from_family = 0
		row.type = "Stepbrother"
		bob.save(ignore_permissions=True)

		rows = [row for row in frappe.get_doc("Person", bob.name).relations if row.person == bill.name]
		self.assertEqual([(row.type, row.from_family) for row in rows], [("Stepbrother", 0)])
		self.assertEqual(self._relations(bill)[bob.name], ("Stepbrother", 1))

	def _correct_by_hand(self, person, other, relation_type):
		person = frappe.get_doc("Person", person.name)
		row = next(row for row in person.relations if row.person == other.name)
		row.from_family = 0
		row.type = relation_type
		person.save(ignore_permissions=True)

	def test_stepfather_gives_the_other_side_stepson(self):
		_family, head, _mom, bob, _bill = self._make_household("Step Household")
		self._correct_by_hand(bob, head, "Stepfather")

		self.assertEqual(self._relations(head)[bob.name], ("Stepson", 1))

	def test_relation_with_no_reverse_type_leaves_the_other_side_blank(self):
		_family, head, _mom, bob, _bill = self._make_household("Reverse Household")
		if not frappe.db.exists("Person Relation Type", "Godfather"):
			frappe.get_doc({"doctype": "Person Relation Type", "type": "Godfather"}).insert(
				ignore_permissions=True
			)
		self._correct_by_hand(bob, head, "Godfather")

		self.assertNotIn(bob.name, self._relations(head))

	def test_sons_wife_is_labelled_and_related_as_an_in_law(self):
		family, head, mom, bob, bill = self._make_household("In-law Household")
		jane = self._make_person("Jane", gender="Female")
		bob = frappe.get_doc("Person", bob.name)
		bob.is_married = 1
		bob.spouse = jane.name
		bob.save(ignore_permissions=True)

		labels = {m.member: m.relationship_to_head for m in frappe.get_doc("Family", family.name).members}
		self.assertEqual(labels[jane.name], "Daughter-in-law")
		self.assertEqual(self._relations(head)[jane.name], ("Daughter-in-law", 1))
		self.assertEqual(self._relations(mom)[jane.name], ("Daughter-in-law", 1))
		self.assertEqual(self._relations(bill)[jane.name], ("Sister-in-law", 1))
		self.assertEqual(
			self._relations(jane),
			{
				bob.name: ("Husband", 0),
				head.name: ("Father-in-law", 1),
				mom.name: ("Mother-in-law", 1),
				bill.name: ("Brother-in-law", 1),
			},
		)

	def test_leaving_family_keeps_its_relations_as_hand_entered(self):
		_family, head, mom, bob, bill = self._make_household("Leaving Household")
		bill = frappe.get_doc("Person", bill.name)
		bill.family = None
		bill.save(ignore_permissions=True)

		self.assertEqual(
			self._relations(bill),
			{head.name: ("Father", 0), mom.name: ("Mother", 0), bob.name: ("Brother", 0)},
		)
		self.assertEqual(self._relations(bob)[bill.name], ("Brother", 0))
		self.assertEqual(self._relations(head)[bill.name], ("Son", 0))

	def test_deleting_a_member_removes_the_rows_about_them(self):
		_family, head, _mom, bob, bill = self._make_household("Deleting Household")
		frappe.delete_doc("Person", bill.name, ignore_permissions=True)

		self.assertNotIn(bill.name, self._relations(bob))
		self.assertNotIn(bill.name, self._relations(head))

	def test_married_son_starts_his_own_family_with_his_wife(self):
		family, head, _mom, bob, _bill = self._make_household("Parents Household")
		jane = self._make_person("Jane", gender="Female")
		bob = frappe.get_doc("Person", bob.name)
		bob.last_name = "Parents"
		bob.is_married = 1
		bob.spouse = jane.name
		bob.save(ignore_permissions=True)

		bob.new_family_from_person()

		self.assertNotEqual(bob.family, family.name)
		self.assertEqual(
			{m.member for m in frappe.get_doc("Family", bob.family).members}, {bob.name, jane.name}
		)
		self.assertNotIn(bob.name, {m.member for m in frappe.get_doc("Family", family.name).members})
		self.assertNotIn(jane.name, {m.member for m in frappe.get_doc("Family", family.name).members})
		self.assertEqual(frappe.db.get_value("Person", jane.name, "family"), bob.family)
		labels = {m.member: m.relationship_to_head for m in frappe.get_doc("Family", bob.family).members}
		self.assertEqual(labels[jane.name], "Wife")
		self.assertEqual(self._relations(bob)[head.name], ("Father", 0))
		self.assertEqual(self._relations(jane)[head.name], ("Father-in-law", 0))

	def test_unknown_gender_gets_no_relation(self):
		family, head, _mom, bob, _bill = self._make_household("Unknown Household")
		child = self._make_person("Kid", gender="Unknown", family=family.name)
		family.reload()
		for member in family.members:
			if member.member == child.name:
				member.relationship_to_head = "Son"
		family.save(ignore_permissions=True)

		self.assertNotIn(child.name, self._relations(bob))
		self.assertEqual(self._relations(head)[child.name], ("Son", 1))
