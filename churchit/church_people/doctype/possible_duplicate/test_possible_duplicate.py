# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.matching import (
	MERGED,
	NOT_A_DUPLICATE,
	Match,
	get_pairs,
	record_possible_duplicates,
	resolve_merged,
)
from churchit.tests.helpers import RollbackEachTest, make_person


class TestPossibleDuplicate(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.jane = make_person("_Test Jane", "Pair").name
		self.janet = make_person("_Test Janet", "Pair").name

	def test_a_pair_is_stored_once_in_name_order_with_its_names(self):
		record_possible_duplicates(self.janet, [Match(self.jane, 90, ("same email",))])
		record_possible_duplicates(self.jane, [Match(self.janet, 85)])

		pairs = get_pairs(self.jane)
		self.assertEqual(len(pairs), 1)
		pair = frappe.get_doc("Possible Duplicate", pairs[0].name)
		first, second = sorted((self.jane, self.janet))
		self.assertEqual((pair.person, pair.other_person), (first, second))
		self.assertEqual(pair.person_name, frappe.db.get_value("Person", first, "full_name"))
		self.assertEqual((pair.score, pair.reasons), (90, "same email"))

	def test_a_pair_marked_not_a_duplicate_is_not_opened_again(self):
		(name,) = record_possible_duplicates(self.jane, [Match(self.janet, 90)])
		frappe.db.set_value("Possible Duplicate", name, "status", NOT_A_DUPLICATE)

		self.assertEqual(record_possible_duplicates(self.janet, [Match(self.jane, 95)]), [])

	def test_after_a_merge_the_merged_pair_closes_and_a_repeated_pair_goes(self):
		june = make_person("_Test June", "Pair").name
		(merged,) = record_possible_duplicates(self.jane, [Match(self.janet, 90)])
		record_possible_duplicates(self.jane, [Match(june, 80)])
		record_possible_duplicates(self.janet, [Match(june, 80)])
		# What a merge of Janet into Jane leaves: every link to Janet now names Jane.
		frappe.db.sql(
			"update `tabPossible Duplicate` set person = %(jane)s where person = %(janet)s",
			{"jane": self.jane, "janet": self.janet},
		)
		frappe.db.sql(
			"update `tabPossible Duplicate` set other_person = %(jane)s where other_person = %(janet)s",
			{"jane": self.jane, "janet": self.janet},
		)

		resolve_merged(self.jane)

		self.assertEqual(frappe.db.get_value("Possible Duplicate", merged, "status"), MERGED)
		self.assertEqual(len(get_pairs(self.jane, june)), 1)

	def test_the_form_compares_the_people_it_may_show(self):
		frappe.db.set_value("Person", self.jane, "nickname", "Janie")
		person = frappe.get_doc("Person", self.janet)
		person.append("emails", {"email_address": "janet.pair@example.com"})
		person.append("phones", {"phone_number": "217-555-0180"})
		person.save()
		(name,) = record_possible_duplicates(self.jane, [Match(self.janet, 90)])

		duplicate = frappe.get_doc("Possible Duplicate", name)
		duplicate.run_method("onload")
		people = duplicate.get_onload().people

		self.assertEqual(set(people), {self.jane, self.janet})
		self.assertEqual(people[self.jane]["nickname"], "Janie")
		self.assertEqual(people[self.janet]["emails"], ["janet.pair@example.com"])
		self.assertEqual(people[self.janet]["phones"], ["217-555-0180"])
