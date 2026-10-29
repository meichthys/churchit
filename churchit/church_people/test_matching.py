# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.matching import find_matches, get_possible_matches, is_same_phone
from churchit.contacts import phone_digits
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_person,
	make_two_churches,
	set_private_people,
)

LAST_NAME = "_Testmatch"


def make_matchable(first_name, last_name=LAST_NAME, emails=(), phones=(), birth_date=None, **values):
	ensure("Life Event Type", {"type": "Birth"})
	return make_person(
		first_name,
		last_name,
		emails=[{"email_address": email} for email in emails],
		phones=[{"phone_number": phone} for phone in phones],
		life_events=[{"event_type": "Birth", "date": birth_date}] if birth_date else [],
		**values,
	).name


def matched(candidate, **arguments):
	return [match.person for match in find_matches(candidate, **arguments)]


class TestFindMatches(RollbackEachTest):
	def test_a_nickname_and_an_email_in_another_case_match(self):
		robert = make_matchable("Robert", emails=["robert.match@example.com"])

		(match,) = find_matches(
			{"first_name": "Bob", "last_name": LAST_NAME, "emails": ["Robert.Match@Example.COM"]}
		)

		self.assertEqual(match.person, robert)
		self.assertEqual(match.reasons, ("nickname of first name", "same last name", "same email"))

	def test_accents_case_and_punctuation_are_ignored(self):
		jose = make_matchable("José", "García", phones=["+1 (217) 555-0142"])
		mary_kate = make_matchable("Mary-Kate", "O'Brien", phones=["+1 (217) 555-0143"])

		self.assertEqual(
			matched({"first_name": "jose", "last_name": "GARCIA", "phones": ["217.555.0142"]}), [jose]
		)
		match = find_matches({"first_name": "Mary Kate", "last_name": "OBrien", "phones": ["2175550143"]})[0]
		self.assertEqual(match.person, mary_kate)
		self.assertIn("same first name", match.reasons)
		self.assertIn("same last name", match.reasons)

	def test_phone_numbers_match_however_they_are_written(self):
		same = [
			("+1 (217) 555-0142", "217.555.0142"),
			("555-0142", "(217) 555-0142"),
			("+44 20 7946 0958", "020 7946 0958"),
		]
		different = [("217-555-0142", "317-555-0142"), ("555-0142", "555-0143"), ("0142", "0142")]

		for number, other in same:
			self.assertTrue(is_same_phone(phone_digits(number), phone_digits(other)), (number, other))
		for number, other in different:
			self.assertFalse(is_same_phone(phone_digits(number), phone_digits(other)), (number, other))

	def test_a_different_birth_date_lowers_the_score_below_the_threshold(self):
		ann = make_matchable("Ann", emails=["ann.match@example.com"], birth_date="1950-03-04")
		candidate = {"first_name": "Ann", "last_name": LAST_NAME, "emails": ["ann.match@example.com"]}

		self.assertEqual(find_matches({**candidate, "birth_date": "1950-03-04"})[0].score, 100)
		self.assertEqual(matched({**candidate, "birth_date": "1980-03-04"}), [])

		frappe.db.set_single_value("People Settings", "match_threshold", 1)
		match = find_matches({**candidate, "birth_date": "1980-03-04"})[0]
		self.assertEqual((match.person, match.score), (ann, 60))
		self.assertIn("different birth date", match.reasons)

	def test_people_who_have_died_are_left_out(self):
		ensure("Life Event Type", {"type": "Death"})
		make_person(
			"Walter",
			LAST_NAME,
			emails=[{"email_address": "walter.match@example.com"}],
			life_events=[{"event_type": "Death", "date": "2024-01-01"}],
		)

		self.assertEqual(
			matched({"first_name": "Walter", "last_name": LAST_NAME, "emails": ["walter.match@example.com"]}),
			[],
		)

	def test_a_family_member_sharing_contact_details_is_not_a_match(self):
		make_matchable("Mary", phones=["217-555-0150"], emails=["home.match@example.com"])

		candidate = {"last_name": LAST_NAME, "phones": ["2175550150"], "emails": ["home.match@example.com"]}
		self.assertEqual(matched({**candidate, "first_name": "Mark"}), [])
		self.assertNotEqual(matched({**candidate, "first_name": "Mary"}), [])

	def test_the_threshold_comes_from_people_settings(self):
		# Same first name, last name and phone: 85.
		john = make_matchable("John", phones=["217-555-0160"])
		candidate = {"first_name": "John", "last_name": LAST_NAME, "phones": ["217-555-0160"]}

		frappe.db.set_single_value("People Settings", "match_threshold", 85)
		self.assertEqual(matched(candidate), [john])
		frappe.db.set_single_value("People Settings", "match_threshold", 90)
		self.assertEqual(matched(candidate), [])

	def test_a_name_change_is_found_by_birth_date_and_nickname(self):
		kate = make_matchable("Katherine", "_Testmarried", birth_date="1985-06-07")

		self.assertEqual(
			matched({"first_name": "Kate", "last_name": LAST_NAME, "birth_date": "1985-06-07"}), []
		)
		frappe.db.set_single_value("People Settings", "match_threshold", 60)
		self.assertEqual(
			matched({"first_name": "Kate", "last_name": LAST_NAME, "birth_date": "1985-06-07"}), [kate]
		)

	def test_exclude_leaves_out_one_person(self):
		ruth = make_matchable("Ruth", birth_date="1960-01-02")
		candidate = {"first_name": "Ruth", "last_name": LAST_NAME, "birth_date": "1960-01-02"}

		self.assertEqual(matched(candidate), [ruth])
		self.assertEqual(matched(candidate, exclude=ruth), [])


class TestMatchesAcrossChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		set_private_people(False)
		cls.manager_a = ensure_user("_test_match_a@example.com", "MatchA", roles=("Church Manager",))
		make_person("MatchA", "Manager", church=cls.branch_a, user=cls.manager_a)
		cls.member = ensure_user("_test_match_member@example.com", "MatchMember")
		cls.mary_a = make_matchable(
			"Mary", birth_date="1970-05-06", phones=["217-555-0170"], church=cls.branch_a
		)
		cls.mary_b = make_matchable(
			"Mary", birth_date="1970-05-06", phones=["217-555-0171"], church=cls.branch_b
		)
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_church_narrows_the_matches_to_its_people(self):
		candidate = {"first_name": "Mary", "last_name": LAST_NAME, "birth_date": "1970-05-06"}

		self.assertEqual(matched(candidate, church=self.branch_a), [self.mary_a])
		self.assertEqual(matched(candidate, church=self.branch_b), [self.mary_b])
		self.assertEqual(sorted(matched(candidate)), sorted([self.mary_a, self.mary_b]))

	def test_the_warning_names_only_people_the_user_may_read(self):
		candidate = {"first_name": "Mary", "last_name": LAST_NAME, "phones": ["(217) 555-0171"]}
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		frappe.set_user(self.manager_a)
		self.assertEqual(get_possible_matches(candidate), [])
		frappe.set_user("Administrator")
		(match,) = get_possible_matches(candidate)
		self.assertEqual((match["person"], match["full_name"]), (self.mary_b, f"Mary {LAST_NAME}"))

	def test_the_warning_names_another_churchs_person_while_the_directory_is_shared(self):
		frappe.set_user(self.manager_a)
		(match,) = get_possible_matches(
			{"first_name": "Mary", "last_name": LAST_NAME, "phones": ["(217) 555-0171"]}
		)
		self.assertEqual(match["person"], self.mary_b)

	def test_a_member_who_cannot_add_people_gets_no_warning(self):
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			get_possible_matches({"first_name": "Mary", "last_name": LAST_NAME, "phones": ["2175550170"]})
