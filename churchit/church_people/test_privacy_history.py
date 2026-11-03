# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
import re

import frappe

from churchit.church_people.privacy import ANONYMIZED, anonymize_person, scrub_history
from churchit.church_people.test_merge import email, make_family
from churchit.patches.v1_0 import forget_team_and_duplicate_history_of_anonymized_people
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)
from churchit.tests.test_desk_ui_hygiene import PERSON_HISTORY_EXCEPTIONS

# Frappe skips Version rows while it runs tests, unless a save asks for them.
SAVE_WITH_HISTORY = {"ignore_permissions": True, "ignore_version": False}
# A Version row writes non-ASCII as \u escapes, which the scrub must still find.
FIRST_NAME = "_Test Zoë"
FULL_NAME = f"{FIRST_NAME} Historia"


def get_history(doc) -> str:
	"""Every Version row of *doc*, as one text that spells non-ASCII out."""
	rows = frappe.get_all("Version", filters={"ref_doctype": doc.doctype, "docname": doc.name}, pluck="data")
	return " ".join(json.dumps(json.loads(data), ensure_ascii=False) for data in rows)


def is_gap(doctype: str) -> bool:
	"""True when PERSON_HISTORY_EXCEPTIONS names the history of *doctype* as a leak still to close."""
	return " gap:" in PERSON_HISTORY_EXCEPTIONS.get(doctype, "")


def rename(person, first_name: str) -> None:
	person.first_name = first_name
	person.save(ignore_permissions=True)


def make_block_with_former_name(person):
	"""A Ministry Team Block of *person* whose history keeps their name from before a rename."""
	block = frappe.get_doc(
		{
			"doctype": "Ministry Team Block",
			"person": person.name,
			"from_date": "2031-01-01",
			"to_date": "2031-01-02",
		}
	).insert(ignore_permissions=True)
	rename(person, FIRST_NAME)
	block.save(**SAVE_WITH_HISTORY)
	return block


class TestHistoryAfterRemovingPersonalData(RollbackEachTest):
	"""Proves by behavior that Remove Personal Data leaves no Version row with the person's name or email.

	A doctype whose PERSON_HISTORY_EXCEPTIONS line is a Gap must still leak, and any other must not. Closing a
	leak makes its test fail until the Gap line is deleted or reworded; the test then stays as the regression check.
	"""

	def assert_forgotten(self, doc, text: str, person) -> None:
		"""*text* is in the history of *doc*, and anonymizing *person* leaves it there only for a Gap line."""
		self.assertIn(text, get_history(doc), "The test must put the text in the history first")

		anonymize_person(person.name)

		self.assertEqual(
			text in get_history(doc),
			is_gap(doc.doctype),
			f"The {doc.doctype} history and its PERSON_HISTORY_EXCEPTIONS line disagree. "
			"A leak needs a Gap line, and a closed leak loses it.",
		)

	def test_a_family_that_keeps_members_forgets_the_persons_first_name(self):
		person = make_person("_Test Anne-Marie", "Historia")
		family = make_family("Historia - _Test Anne-Marie", person, make_person("_Test Wife", "Historia"))
		family.family_name = "Historia Household - _Test Anne-Marie"
		family.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(family, "_Test Anne-Marie", person)
		self.assertEqual(frappe.db.get_value("Family", family.name, "family_name"), "Historia Household")

	def test_a_spouse_forgets_the_persons_name(self):
		person = make_person(FIRST_NAME, "Historia")
		spouse = make_person("_Test Spouse", "Historia")
		spouse.update({"spouse": person.name, "marital_status": "Married"})
		spouse.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(spouse, FULL_NAME, person)

	def test_another_member_forgets_the_family_name_that_held_the_persons_first_name(self):
		person = make_person("_Test Anne-Marie", "Historia")
		family = make_family("Historia - _Test Anne-Marie", person, make_person("_Test Wife", "Historia"))
		child = make_person("_Test Child", "Historia")
		child.family = family.name
		child.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(child, "Historia - _Test Anne-Marie", person)

	def test_a_collection_forgets_the_email_of_a_donor_added_after_the_first_save(self):
		address = "_test.history@example.com"
		donor = make_person(FIRST_NAME, "Historia", emails=[email(address)])
		gift = {
			"fund": ensure("Fund", {"fund": "_Test History Fund"}),
			"payment_type": ensure("Payment Type", {"type": "Cash"}),
			"amount": 5,
		}
		collection = frappe.get_doc(
			{"doctype": "Collection", "date": "2031-01-05 10:00:00", "expected_total": 5, "donations": [gift]}
		).insert(ignore_permissions=True)
		collection.append("donations", {**gift, "person": donor.name, "person_email": address})
		collection.expected_total = 10
		collection.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(collection, address, donor)

	def test_a_function_forgets_a_title_typed_with_an_attendees_name(self):
		person = make_person(FIRST_NAME, "Historia")
		checked_in = ensure("Function Attendance Type", {"type": "Checked-In"})
		function = make_function(
			f"Baptism of {FULL_NAME}",
			start_date=frappe.utils.today(),
			attendance=[{"person": person.name, "attendance_type": checked_in}],
		)
		function.function_name = "_Test History Baptism"
		function.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(function, FULL_NAME, person)

	def test_a_missionary_forgets_a_title_typed_with_the_persons_name(self):
		person = make_person(FIRST_NAME, "Historia")
		missionary = frappe.get_doc(
			{"doctype": "Missionary", "title": FULL_NAME, "people": [{"person": person.name}]}
		).insert(ignore_permissions=True)
		missionary.title = "_Test History Mission"
		missionary.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(missionary, FULL_NAME, person)

	def test_a_ministry_forgets_the_name_of_its_coordinator(self):
		person = make_person(FIRST_NAME, "Historia")
		ministry = frappe.get_doc({"doctype": "Ministry", "ministry_name": "_Test History Ministry"}).insert(
			ignore_permissions=True
		)
		ministry.team_coordinator = person.name
		ministry.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(ministry, FULL_NAME, person)

	def test_a_team_assignment_forgets_the_name_the_person_had_before_a_rename(self):
		person = make_person("_Test Former", "Historia")
		position = make_team_position("_Test History Usher", [person.name])
		function = make_function(
			"_Test History Service", start_date=frappe.utils.add_days(frappe.utils.today(), 7)
		)
		assignment = make_team_assignment(function.name, position.name, person.name)
		rename(person, FIRST_NAME)
		assignment.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(assignment, "_Test Former Historia", person)

	def test_a_team_block_forgets_the_name_the_person_had_before_a_rename(self):
		person = make_person("_Test Former", "Historia")
		block = make_block_with_former_name(person)

		self.assert_forgotten(block, "_Test Former Historia", person)

	def test_a_possible_duplicate_forgets_the_name_the_person_had_before_a_rename(self):
		person = make_person("_Test Former", "Historia")
		pair = frappe.get_doc(
			{
				"doctype": "Possible Duplicate",
				"person": make_person("_Test Other", "Historia").name,
				"other_person": person.name,
				"status": "Open",
			}
		).insert(ignore_permissions=True)
		rename(person, FIRST_NAME)
		pair.save(**SAVE_WITH_HISTORY)

		self.assert_forgotten(pair, "_Test Former Historia", person)


class TestScrubHistory(RollbackEachTest):
	def test_a_text_that_held_only_a_removed_email_reads_as_empty_not_null(self):
		address = "_test.history@example.com"
		person = make_person(FIRST_NAME, "Historia")
		version = frappe.get_doc(
			{
				"doctype": "Version",
				"ref_doctype": "Person",
				"docname": person.name,
				"data": frappe.as_json({"changed": [["primary_email", "", address]]}),
			}
		).insert(ignore_permissions=True)

		scrub_history([("Person", person.name)], [(re.compile(re.escape(address)), "")], [address])

		data = json.loads(frappe.db.get_value("Version", version.name, "data"))
		self.assertEqual(data["changed"], [["primary_email", "", ""]])

	def test_a_name_with_a_suffix_is_anonymized_whole(self):
		person = make_person(FIRST_NAME, "Historia", suffix="Jr.")
		missionary = frappe.get_doc(
			{"doctype": "Missionary", "title": f"{FULL_NAME} Jr.", "people": [{"person": person.name}]}
		).insert(ignore_permissions=True)
		missionary.title = "_Test History Mission"
		missionary.save(**SAVE_WITH_HISTORY)

		anonymize_person(person.name)

		self.assertIn(ANONYMIZED, get_history(missionary))
		self.assertNotIn("Jr.", get_history(missionary))


class TestForgetHistoryOfPeopleAnonymizedBefore(RollbackEachTest):
	def test_the_patch_forgets_the_team_block_history_of_a_person_anonymized_before(self):
		person = make_person("_Test Former", "Historia")
		block = make_block_with_former_name(person)
		frappe.db.set_value("Person", person.name, "first_name", ANONYMIZED)
		self.assertIn("_Test Former Historia", get_history(block))

		forget_team_and_duplicate_history_of_anonymized_people.execute()

		self.assertNotIn("_Test Former Historia", get_history(block))
