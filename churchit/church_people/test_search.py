# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.client import validate_link_and_fetch
from frappe.desk.search import search_link

from churchit.church_people.privacy import ANONYMIZED, anonymize_person
from churchit.church_people.search import search_people
from churchit.church_people.test_matching import make_matchable
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_person,
	make_two_churches,
	set_private_people,
)

SEARCH_PEOPLE = "churchit.church_people.search.search_people"


@contextmanager
def searching_people_by_contact():
	"""The standard_queries hook as hooks.py registers it.

	Frappe's Link search reads it as `frappe.get_hooks().standard_queries`, which `patch_hooks` cannot reach.
	"""
	hooks = frappe._dict(frappe.get_hooks())
	hooks.standard_queries = {**(hooks.standard_queries or {}), "Person": [SEARCH_PEOPLE]}
	get_hooks = frappe.get_hooks

	def patched(hook=None, *args, **kwargs):
		return hooks if hook is None else get_hooks(hook, *args, **kwargs)

	with patch.object(frappe, "get_hooks", patched):
		yield


def found(txt, **arguments):
	return [row["value"] for row in search_link("Person", txt, **arguments)]


class TestPersonSearch(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.anna = make_matchable(
			"Anna", "_Testsearch", emails=["anna.search@example.com"], phones=["+1 (217) 555-0190"]
		)
		self.ben = make_matchable("Ben", "_Testsearch", phones=["217-555-0191"], gender="Male")

	def test_a_person_is_found_by_phone_however_it_is_typed(self):
		with searching_people_by_contact():
			for typed in ("217-555-0190", "2175550190", "(217) 555 0190", "555-0190"):
				self.assertEqual(found(typed), [self.anna], typed)

	def test_a_person_is_found_by_email_in_any_case(self):
		with searching_people_by_contact():
			self.assertEqual(found("Anna.Search@Example.com"), [self.anna])
			self.assertEqual(found("anna.search@"), [self.anna])

	def test_names_are_found_as_before_and_filters_still_apply(self):
		with searching_people_by_contact():
			self.assertEqual(sorted(found("_Testsearch")), sorted([self.anna, self.ben]))
			self.assertEqual(found("_Testsearch", filters={"gender": "Male"}), [self.ben])
			self.assertEqual(found("555-019", filters={"gender": "Male"}), [self.ben])
			self.assertEqual(len(found("_Testsearch", page_length=1)), 1)

	def test_a_person_is_found_by_their_middle_name(self):
		cora = make_matchable("Cora", "_Testsearch", middle_name="_Testmiddle")
		with searching_people_by_contact():
			self.assertEqual(found("_Testmiddle"), [cora])

	def test_digits_inside_a_name_are_not_a_phone_search(self):
		with searching_people_by_contact():
			self.assertEqual(found("Anna 2175550190"), [])

	def test_a_typed_name_still_validates_as_a_link(self):
		with searching_people_by_contact():
			frappe.local.request = frappe._dict(method="POST")
			self.addCleanup(delattr, frappe.local, "request")
			self.assertEqual(validate_link_and_fetch("Person", self.anna).get("name"), self.anna)

	def test_a_person_whose_data_was_removed_is_never_offered(self):
		frappe.db.set_value("Person", self.anna, "envelope_number", "_T90418")
		anonymize_person(self.anna)

		with searching_people_by_contact():
			self.assertNotIn(self.anna, found(""))
			self.assertEqual(found("", filters={"name": self.anna}), [])
			for typed in ("_T90418", "217-555-0190", ANONYMIZED):
				self.assertNotIn(self.anna, found(typed), typed)
			self.assertEqual(found("_Testsearch"), [self.ben])


class TestPersonSearchAcrossChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_search_a@example.com", "SearchA", roles=("Church Manager",))
		make_person("SearchA", "Manager", church=cls.branch_a, user=cls.manager_a)
		cls.person_b = make_matchable(
			"Carol", "_Testsearch", emails=["carol.search@example.com"], church=cls.branch_b
		)
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_private_directory_hides_another_churchs_person_from_a_contact_search(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		frappe.set_user(self.manager_a)
		with searching_people_by_contact():
			self.assertEqual(found("carol.search@example.com"), [])
		frappe.set_user("Administrator")
		with searching_people_by_contact():
			self.assertEqual(found("carol.search@example.com"), [self.person_b])

	def test_a_person_of_another_church_is_offered_with_that_churchs_title(self):
		frappe.set_user("Administrator")
		with searching_people_by_contact():
			rows = search_link("Person", "_Testsearch")

		self.assertIn(frappe.db.get_value("Church", self.branch_b, "church_name"), rows[0]["description"])

	def test_a_person_of_the_readers_church_is_offered_without_a_church(self):
		person_a = make_matchable("Dora", "_Testsearch", church=self.branch_a)
		frappe.set_user(self.manager_a)
		with searching_people_by_contact():
			rows = [row for row in search_link("Person", "_Testsearch") if row["value"] == person_a]

		self.assertNotIn(frappe.db.get_value("Church", self.branch_a, "church_name"), rows[0]["description"])

	def test_a_search_as_dicts_still_sorts_and_names_the_church(self):
		frappe.set_user("Administrator")
		rows = search_people("Person", "_Testsearch", "name", 0, 20, None, as_dict=True)

		self.assertEqual(rows[0].name, self.person_b)
		self.assertEqual(rows[0].church, frappe.db.get_value("Church", self.branch_b, "church_name"))


class TestDeceasedMarker(RollbackEachTest):
	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Life Event Type", "Death"):
			frappe.get_doc({"doctype": "Life Event Type", "type": "Death"}).insert(ignore_permissions=True)

	def test_a_person_who_died_is_offered_with_a_deceased_description(self):
		living = make_person("_Testsearchmark", "Living")
		departed = make_person(
			"_Testsearchmark",
			"Departed",
			life_events=[{"event_type": "Death", "date": "2020-01-01"}],
		)
		with searching_people_by_contact():
			rows = {row["value"]: row for row in search_link("Person", "_Testsearchmark")}

		self.assertIn("Deceased", rows[departed.name]["description"])
		self.assertNotIn("Deceased", rows[living.name].get("description", ""))

	def test_a_search_as_dicts_marks_the_deceased_too(self):
		departed = make_person(
			"_Testsearchmark",
			"Departed",
			life_events=[{"event_type": "Death", "date": "2020-01-01"}],
		)
		rows = search_people("Person", "_Testsearchmark", "name", 0, 20, None, as_dict=True)

		self.assertEqual([(row.name, row.is_deceased) for row in rows], [(departed.name, "Deceased")])
