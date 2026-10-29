# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.matching import Match, record_possible_duplicates
from churchit.church_people.report.people_data_quality import people_data_quality as report
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_address,
	make_person,
	make_two_churches,
)

LAST_NAME = "_Testquality"


def problems(filters=None):
	"""``{(person, problem, detail)}`` of the report's rows about the test's people."""
	_columns, rows = report.execute(filters or {})
	people = set(frappe.get_all("Person", filters={"last_name": LAST_NAME}, pluck="name"))
	return {(row["person"], row["problem"], row["detail"]) for row in rows if row["person"] in people}


def make_family(family_name, **values):
	return frappe.get_doc({"doctype": "Family", "family_name": family_name, **values}).insert().name


class TestPeopleDataQuality(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.family = make_family("_Test Quality Family", phones=[{"phone_number": "217-555-0200"}])

	def make(self, first_name, **values):
		return make_person(first_name, LAST_NAME, **{"family": self.family, **values}).name

	def test_a_person_with_nothing_to_fix_is_not_listed(self):
		self.make("Tidy", emails=[{"email_address": "tidy.quality@example.com"}])

		self.assertEqual(problems(), set())

	def test_someone_with_no_contact_details_anywhere_cannot_be_reached(self):
		reached_through_family = self.make("Kid")
		lone = make_person("Lone", LAST_NAME).name

		self.assertEqual(problems(), {(lone, "No Way to Reach", None), (lone, "No Family", None)})
		self.assertNotIn(reached_through_family, {person for person, _problem, _detail in problems()})

	def test_invalid_emails_and_phones_are_listed_with_their_value(self):
		person = frappe.get_doc(
			"Person",
			self.make(
				"Typo",
				emails=[{"email_address": "typo.quality@example.com"}],
				phones=[{"phone_number": "217-555-0201"}],
			),
		)
		frappe.db.set_value("Email Address", person.emails[0].name, "email_address", "typo.quality@example")
		frappe.db.set_value("Phone Number", person.phones[0].name, "phone_number", "555-01")

		self.assertEqual(
			problems(),
			{
				(person.name, "Invalid Email", "typo.quality@example"),
				(person.name, "Invalid Phone Number", "555-01"),
			},
		)

	def test_returned_mail_names_the_address(self):
		address = make_address("_Test Quality Address").name
		person = self.make(
			"Moved",
			emails=[{"email_address": "moved.quality@example.com"}],
			addresses=[{"address": address, "is_returned_mail": 1}],
		)

		self.assertEqual(problems(), {(person, "Mail Returned", address)})

	def test_a_bounced_email_names_the_address(self):
		person = frappe.get_doc(
			"Person",
			self.make(
				"Bounced",
				emails=[
					{"email_address": "gone.quality@example.com"},
					{"email_address": "kept.quality@example.com"},
				],
			),
		)
		frappe.db.set_value("Email Address", person.emails[0].name, "is_bounced", 1)

		self.assertEqual(problems(), {(person.name, "Email Bounced", "gone.quality@example.com")})
		self.assertEqual(problems({"problem": "Mail Returned"}), set())

	def test_both_people_in_an_open_possible_duplicate_are_listed(self):
		ruth = self.make("Ruth", emails=[{"email_address": "ruth.quality@example.com"}])
		other = self.make("Ruth", emails=[{"email_address": "ruth2.quality@example.com"}])
		record_possible_duplicates(ruth, [Match(other, 85)])

		full_name = f"Ruth {LAST_NAME}"
		self.assertEqual(
			problems(), {(ruth, "Possible Duplicate", full_name), (other, "Possible Duplicate", full_name)}
		)

	def test_a_child_needs_a_birth_date(self):
		child = self.make("Child")
		frappe.db.set_value("Person", child, "life_stage", "Child")

		self.assertEqual(problems(), {(child, "Child Without Birth Date", None)})

	def test_the_problem_filter_and_the_dead_narrow_the_list(self):
		ensure("Life Event Type", {"type": "Death"})
		lone = make_person("Lone", LAST_NAME).name
		make_person("Gone", LAST_NAME, life_events=[{"event_type": "Death", "date": "2024-01-01"}])

		self.assertEqual(problems({"problem": "No Family"}), {(lone, "No Family", None)})


class TestPeopleDataQualityAcrossChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch_a, branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_quality_a@example.com", "QualityA", roles=("Church Manager",))
		make_person("QualityA", "Manager", church=branch_a, user=cls.manager_a)
		cls.person_a = make_person("Alpha", LAST_NAME, church=branch_a).name
		cls.person_b = make_person("Bravo", LAST_NAME, church=branch_b).name
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_church_sees_only_its_own_peoples_problems(self):
		frappe.set_user(self.manager_a)
		listed = {person for person, _problem, _detail in problems()}

		self.assertIn(self.person_a, listed)
		self.assertNotIn(self.person_b, listed)
