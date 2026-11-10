# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Explain Match and Suggest Fixes send only the match evidence and the flagged values, never merge,
and leave every save to the person.

Tests never call a model: runner.start is patched, and each check runs as the caller.
"""

import inspect
import json
import re
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.client import set_value

from churchit.ai import runner
from churchit.ai.test_runner import WRITER, FlowRunnerTestCase, flow_session, staff_user
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people import ai_actions
from churchit.church_people.matching import POSSIBLE_DUPLICATE, Match, record_possible_duplicates
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.church_people.test_ai_actions import data_of, prompt_of, run_action
from churchit.tests.helpers import ensure_user, make_person, make_two_churches, pop_logs

LAST_NAME = "_Test AI Dupes"
REASONS = ("nickname of first name", "same last name", "same email")


def make_pair(church: str, first: str = "Jonathan", other: str = "Jon", **values) -> tuple[str, str, str]:
	"""(pair, person, other_person) of two people of *church* that the matcher paired."""
	one = make_person(first, LAST_NAME, church=church, **values).name
	two = make_person(other, LAST_NAME, church=church, **values).name
	(pair,) = record_possible_duplicates(one, [Match(two, 85, REASONS)])
	doc = frappe.get_doc(POSSIBLE_DUPLICATE, pair)
	return pair, doc.person, doc.other_person


def make_invalid_email(person, email: str) -> str:
	"""Give *person* an email row holding *email*, which a save would refuse (as an old import left it)."""
	person.append("emails", {"email_address": "placeholder@example.com"})
	person.save(ignore_permissions=True)
	row = person.emails[-1].name
	frappe.db.set_value("Email Address", row, "email_address", email)
	return row


class DuplicateTestCase(AITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.editor = ensure_user("_test_ai_dupes_editor@example.com", "AI Editor", ["Church People Editor"])
		set_user_church(cls.editor, cls.branch_a)


class TestExplainDuplicate(DuplicateTestCase):
	def setUp(self):
		super().setUp()
		self.pair, self.person, self.other = make_pair(self.branch_a)

	def test_a_people_editor_gets_the_explanation_from_the_evidence_only(self):
		spouses = [make_person(f"Secretia {n}", "Spousename", church=self.branch_a).name for n in (1, 2)]
		for person, spouse, notes in zip(
			(self.person, self.other), spouses, ("Peanuts", "Bee stings"), strict=True
		):
			frappe.db.set_value("Person", person, {"spouse": spouse, "medical_notes": notes})

		_result, call = run_action(self.editor, ai_actions.explain_duplicate, self.pair)

		data = data_of(call)
		self.assertIn("- nickname of first name: +30", data)
		self.assertIn("- same email: +45", data)
		self.assertIn("Score: 85 of 100", data)
		self.assertRegex(data, r"- first_name \(First Name\): A = Jon(athan)? \| B = Jon(athan)?")
		for value in ("Spousename", "Peanuts", "Bee stings", "medical_notes", "spouse"):
			self.assertNotIn(value, prompt_of(call))
		self.assertEqual(call.kwargs["sends"], ("Person", POSSIBLE_DUPLICATE))
		self.assertEqual(call.kwargs["reference_name"], self.pair)

	def test_a_manager_never_sends_health_fields(self):
		for person, notes in zip((self.person, self.other), ("Peanuts", "Bee stings"), strict=True):
			frappe.db.set_value("Person", person, {"medical_notes": notes, "alergies": notes})

		_result, call = run_action(self.manager, ai_actions.explain_duplicate, self.pair)

		for value in ("Peanuts", "Bee stings", "alergies"):
			self.assertNotIn(value, prompt_of(call))

	def test_a_manager_never_sends_the_envelope_number(self):
		for person, number in zip((self.person, self.other), ("ENV-4417", "ENV-9903"), strict=True):
			frappe.db.set_value("Person", person, "envelope_number", number)

		_result, call = run_action(self.manager, ai_actions.explain_duplicate, self.pair)

		for value in ("ENV-4417", "ENV-9903", "envelope_number"):
			self.assertNotIn(value, prompt_of(call))

	def test_the_pair_and_each_person_sent_are_logged(self):
		filters = {
			"method": f"AI: {ai_actions.DUPLICATE_EXPLANATION}",
			"reference_document": ("in", [self.pair, self.person, self.other]),
		}
		pop_logs("Access Log", filters)
		run_action(self.editor, ai_actions.explain_duplicate, self.pair)
		self.assertEqual(len(pop_logs("Access Log", filters)), 3)

	def test_the_check_keeps_only_one_of_the_two_values_of_a_differing_field(self):
		first_name = frappe.db.get_value("Person", self.person, "first_name")
		answer = {
			"pair": self.pair,
			"explanation": ["They share an email.", "", 7],
			"keep": [
				{"field": "first_name", "value": "Johnny"},
				{"field": "first_name", "value": first_name},
				{"field": "first_name", "value": "Jon"},
				{"field": "medical_notes", "value": "Peanuts"},
				{"field": "no_such_field", "value": "x"},
			],
		}

		result = as_user(self.editor, ai_actions.check_duplicate_explanation, answer)

		self.assertEqual(result["explanation"], ["They share an email."])
		self.assertEqual(
			result["keep"],
			[{"fieldname": "first_name", "label": "First Name", "value": first_name, "record": "A"}],
		)

	def test_a_malformed_answer_is_refused(self):
		check = ai_actions.check_duplicate_explanation
		for answer in (
			{"pair": [self.pair], "explanation": ["x"]},
			{"pair": self.pair, "explanation": "Same"},
		):
			with self.subTest(answer=answer):
				self.assertRaises(frappe.ValidationError, as_user, self.editor, check, answer)

	def test_the_ai_dialog_offers_no_merge(self):
		self.assertNotIn("merge_people", inspect.getsource(ai_actions))
		script = Path(
			frappe.get_app_path(
				"churchit", "church_people", "doctype", "possible_duplicate", "possible_duplicate.js"
			)
		).read_text()
		explain = re.search(r"function explain_match\(frm\) \{(.*?)\n\}", script, re.DOTALL).group(1)
		self.assertNotIn("on_use", explain)
		self.assertNotIn("merge", explain.replace("before you merge", "").replace("never merges", ""))


class TestDuplicateRefusals(DuplicateTestCase):
	def test_an_excluded_person_a_church_that_keeps_away_and_another_church_are_refused(self):
		excluded, _person, _other = make_pair(self.branch_a, "Ezekiel", "Zeke")
		frappe.db.set_value("Person", _other, "exclude_from_ai", 1)
		theirs = make_pair(self.branch_b, "Bartholomew", "Bart")[0]
		kept = make_pair(self.branch_a, "Katherine", "Kate")[0]

		for pair, error in ((excluded, frappe.PermissionError), (theirs, frappe.PermissionError)):
			with self.subTest(pair=pair):
				self.assertRaises(error, run_action, self.editor, ai_actions.explain_duplicate, pair)
		frappe.db.set_value("Church", self.branch_a, "keep_away_from_ai", 1)
		self.assertRaises(frappe.PermissionError, run_action, self.editor, ai_actions.explain_duplicate, kept)

	def test_ai_off_and_a_member_are_refused(self):
		pair = make_pair(self.branch_a)[0]
		self.assertRaises(frappe.PermissionError, run_action, self.member, ai_actions.explain_duplicate, pair)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, run_action, self.editor, ai_actions.explain_duplicate, pair)


class TestSuggestQualityFixes(DuplicateTestCase):
	def setUp(self):
		super().setUp()
		self.anna = make_person("Annabeth", LAST_NAME, church=self.branch_a)
		self.anna_row = make_invalid_email(self.anna, "annabeth@example,com")
		self.left_out = make_person("Leftina", LAST_NAME, church=self.branch_a, exclude_from_ai=1)
		make_invalid_email(self.left_out, "leftina@example,com")
		self.theirs = make_person("Bettina", LAST_NAME, church=self.branch_b)
		self.their_row = make_invalid_email(self.theirs, "bettina@example,com")

	def test_only_the_flagged_values_of_people_the_editor_may_fix_are_sent(self):
		_result, call = run_action(
			self.editor, ai_actions.suggest_quality_fixes, {"problem": "Invalid Email"}
		)

		items = json.loads(data_of(call))
		self.assertIn(
			{
				"person": self.anna.name,
				"row": self.anna_row,
				"problem": "Invalid Email",
				"value": "annabeth@example,com",
			},
			items,
		)
		values = {item["value"] for item in items}
		self.assertNotIn("leftina@example,com", values)
		self.assertNotIn("bettina@example,com", values)
		for name in ("Annabeth", LAST_NAME, "Leftina"):
			self.assertNotIn(name, prompt_of(call))
		self.assertEqual(call.kwargs["sends"], ("Person",))

	def test_no_more_than_max_fixes_rows_are_sent(self):
		make_invalid_email(make_person("Zeline", LAST_NAME, church=self.branch_a), "zeline@example,com")
		with patch.object(ai_actions, "MAX_FIXES", 1):
			_result, call = run_action(
				self.editor, ai_actions.suggest_quality_fixes, {"problem": "Invalid Email"}
			)
		self.assertEqual(len(json.loads(data_of(call))), 1)

	def test_the_check_keeps_valid_fixes_of_rows_the_editor_may_save(self):
		answer = {
			"fixes": [
				{"person": self.anna.name, "row": self.anna_row, "value": "annabeth@example.com"},
				{"person": self.anna.name, "row": self.anna_row, "value": "still@wrong@"},
				{"person": self.theirs.name, "row": self.their_row, "value": "bettina@example.com"},
				{
					"person": self.left_out.name,
					"row": self.left_out.emails[-1].name,
					"value": "l@example.com",
				},
			]
		}

		result = as_user(self.editor, ai_actions.check_quality_fixes, answer)

		self.assertEqual(
			result["fixes"],
			[
				{
					"person": self.anna.name,
					"person_name": self.anna.full_name,
					"doctype": "Email Address",
					"row": self.anna_row,
					"fieldname": "email_address",
					"old": "annabeth@example,com",
					"value": "annabeth@example.com",
					"problem": "Invalid Email",
				}
			],
		)

	def test_a_ticked_fix_saves_through_the_normal_save_and_another_churchs_is_refused(self):
		as_user(
			self.editor, set_value, "Email Address", self.anna_row, "email_address", "annabeth@example.com"
		)
		self.assertEqual(
			frappe.db.get_value("Email Address", self.anna_row, "email_address"), "annabeth@example.com"
		)

		self.assertRaises(
			frappe.PermissionError,
			as_user,
			self.editor,
			set_value,
			"Email Address",
			self.their_row,
			"email_address",
			"bettina@example.com",
		)

	def test_a_report_with_nothing_to_fix_and_a_member_are_refused(self):
		self.assertRaises(
			frappe.ValidationError,
			run_action,
			self.editor,
			ai_actions.suggest_quality_fixes,
			{"problem": "No Family"},
		)
		self.assertRaises(frappe.PermissionError, run_action, self.member, ai_actions.suggest_quality_fixes)


class TestDuplicatesOnFlow(FlowRunnerTestCase):
	"""People records need a No training, Zero retention or Local model. Needs Flow."""

	def test_explain_and_fixes_run_on_writer_and_need_a_model_that_keeps_records(self):
		church_a = make_two_churches()[1]
		editor = staff_user(
			"_test_ai_dupes_flow@example.com", church_a, ("Church People Editor", "Flow User")
		)
		pair = make_pair(church_a, "Flowrence", "Flo")[0]
		make_invalid_email(make_person("Flowanna", LAST_NAME, church=church_a), "flowanna@example,com")

		frappe.set_user(editor)
		for function, args in (
			(ai_actions.explain_duplicate, (pair,)),
			(ai_actions.suggest_quality_fixes, ()),
		):
			with self.subTest(function.__name__):
				self.set_labels("May train", "May train")
				self.assertRaises(frappe.PermissionError, function, *args)
				self.set_labels("No training", "May train")
				with flow_session() as new_session:
					function(*args)
				self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")
				self.assertEqual(new_session.call_args.args[0].name, WRITER)
