# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's own AI actions on people send only what the caller may read, to the agent the records
need, and check the answer as the caller.

Tests never call a model: runner.start is patched, and each check runs as the runner's completion
runs it, as the caller.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.importer import INSERT

from churchit.ai import drafts, runner
from churchit.ai.test_runner import PRIVATE_WORK, STAFF, WRITER, FlowRunnerTestCase, flow_session
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people import ai, ai_actions
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.church_people.test_notes import make_category
from churchit.tests.helpers import (
	ensure,
	ensure_user,
	make_address,
	make_person,
	make_two_churches,
	pop_logs,
)

LAST_NAME = "_Test AI Actions"
START = "churchit.ai.runner.start"
TOKEN = {"token": "a" * 32}


def run_action(user, function, *args, **kwargs):
	"""*function* as *user* with runner.start patched: (what it returned, start's arguments)."""
	with patch(START, return_value=TOKEN) as start:
		result = as_user(user, function, *args, **kwargs)
	return result, start.call_args


def prompt_of(call) -> str:
	return call.args[1]


def data_of(call) -> str:
	"""The data block of the prompt, the only place text from records goes."""
	return re.search(r"<data[^>]*>\n(.*)\n</data>", prompt_of(call), re.DOTALL).group(1)


class ActionTestCase(AITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.care = ensure_user(
			"_test_ai_actions_carer@example.com", "AI Care", ["Church Staff", "Church Pastoral Care"]
		)
		set_user_church(cls.care, cls.branch_a)


class TestTheRefusals(ActionTestCase):
	def actions(self):
		person = make_person("Refused", LAST_NAME, church=self.branch_a).name
		return (
			(ai_actions.describe_people, ("members in a group",)),
			(ai_actions.brief, ("Person", person)),
			(ai_actions.draft_note, (person, "Visited today.")),
			(ai_actions.suggest_import_mapping, ("no-such-import",)),
		)

	def test_a_website_user_is_refused_every_action(self):
		for function, args in self.actions():
			with self.subTest(function.__name__):
				self.assertRaises(frappe.PermissionError, run_action, self.member, function, *args)

	def test_every_action_is_refused_while_ai_is_off(self):
		actions = self.actions()
		set_ai(0)
		for function, args in actions:
			with self.subTest(function.__name__):
				self.assertRaises(frappe.PermissionError, run_action, self.manager, function, *args)


class TestDescribePeople(ActionTestCase):
	def test_the_prompt_holds_fields_and_group_names_but_no_person(self):
		for church in (self.branch_a, self.branch_b):
			make_person("Zebulon", "Quackenbush", church=church, medical_notes="Peanut allergy")
		group = {"doctype": "Group", "group_name": "_Test AI Describe Youth", "church": self.branch_a}
		frappe.get_doc(group).insert(ignore_permissions=True)
		make_address("_Test AI Quackenbush Home", address_line1="12 Larkspur Lane")

		_result, call = run_action(self.manager, ai_actions.describe_people, "youth who came last month")

		prompt = prompt_of(call)
		self.assertNotIn("Quackenbush", prompt)
		self.assertNotIn("Zebulon", prompt)
		self.assertNotIn("Larkspur", prompt)
		self.assertNotIn("medical_notes", prompt)
		self.assertIn("_Test AI Describe Youth", prompt)
		self.assertIn("last_attended_on: Last Attended (Date)", prompt)
		self.assertIn("last month", prompt)
		self.assertEqual(call.kwargs.get("sends", ()), ())
		self.assertIn("youth who came last month", data_of(call))

	def test_a_field_the_caller_may_not_read_is_not_offered(self):
		_result, call = run_action(self.staff, ai_actions.describe_people, "lapsed givers")

		self.assertNotIn("is_lapsed_giver", prompt_of(call))

	def test_the_answer_is_counted_in_the_callers_churches_and_put_in_words(self):
		for church in (self.branch_a, self.branch_b):
			make_person("Counted", LAST_NAME, church=church)
		answer = {"filters": [["last_name", "=", LAST_NAME]]}

		result = as_user(self.manager, ai_actions.check_people_filters, answer)

		self.assertEqual(result["count"], 1)
		self.assertEqual(result["words"], [f"Last Name is {LAST_NAME}"])
		self.assertIn(ai.LIVING, result["filters"])
		self.assertIn("church", [row[1] for row in result["filters"]])
		self.assertEqual(len(result["notes"]), 2)

	def test_a_wrong_answer_is_refused(self):
		for answer, error in (
			({"filters": []}, frappe.ValidationError),
			({"filters": [["no_such_field", "=", 1]]}, frappe.ValidationError),
			({"filters": [["is_lapsed_giver", "=", 1]]}, frappe.PermissionError),
		):
			with self.subTest(answer=answer):
				self.assertRaises(error, as_user, self.staff, ai_actions.check_people_filters, answer)

	def test_the_runner_reads_a_fenced_answer_through_the_check(self):
		make_person("Fenced", LAST_NAME, church=self.branch_a)
		output = '```json\n{"filters": [["first_name", "=", "Fenced"]]}\n```'
		run = frappe._dict(name="_test-run", status="Completed", output=output)

		result = as_user(self.manager, runner.get_result, run, f"{ai_actions.CHECKS}.check_people_filters")

		self.assertEqual(result["count"], 1)


class TestBriefMe(ActionTestCase):
	def make_visited(self, first_name):
		person = make_person(first_name, LAST_NAME, church=self.branch_a, medical_notes="Peanut allergy")
		frappe.db.set_value("Person", person.name, {"is_lapsed_giver": 1, "open_care_requests": 2})
		visit_type = ensure("Visit Type", {"type": "_Test AI Home"})
		visit = {"doctype": "Visitation Log", "person": person.name, "visit_type": visit_type}
		frappe.get_doc({**visit, "church": self.branch_a}).insert(ignore_permissions=True)
		return person.name

	def test_staff_send_only_what_they_read_and_no_links(self):
		person = self.make_visited("Briefed")

		result, call = run_action(self.staff, ai_actions.brief, "Person", person)

		facts = json.loads(data_of(call))
		self.assertEqual(facts["summary"]["full_name"], f"Briefed {LAST_NAME}")
		self.assertFalse({"is_lapsed_giver", "open_care_requests"} & set(facts["summary"]))
		self.assertNotIn("Peanut", prompt_of(call))
		self.assertNotIn("http", data_of(call))
		self.assertEqual(call.kwargs["sends"], ("Person",))
		self.assertEqual(result["token"], TOKEN["token"])

	def test_a_visit_the_caller_reads_makes_it_a_private_run_with_its_link(self):
		person = self.make_visited("Visited")

		result, call = run_action(self.care, ai_actions.brief, "Person", person)

		self.assertEqual(json.loads(data_of(call))["summary"]["open_care_requests"], 2)
		self.assertEqual(call.kwargs["sends"], ("Care Request", "Person", "Visitation Log"))
		self.assertTrue(any("/desk/visitation-log/" in source["url"] for source in result["sources"]))
		self.assertTrue(call.kwargs["check"].endswith(".check_brief"))

	def test_a_giving_fact_makes_it_a_private_run_and_a_fact_of_no_value_is_left_out(self):
		"""The Person summary works out gifts, care and background checks from their private records."""
		person = self.make_visited("Giver")
		finance = ensure_user(
			"_test_ai_actions_finance@example.com", "AI Finance", ["Church Staff", "Church Finance"]
		)
		set_user_church(finance, self.branch_a)

		_result, call = run_action(finance, ai_actions.brief, "Person", person)
		self.assertEqual(json.loads(data_of(call))["summary"]["is_lapsed_giver"], 1)
		self.assertEqual(call.kwargs["sends"], ("Collection", "Person"))

		frappe.db.set_value("Person", person, "is_lapsed_giver", 0)
		_result, call = run_action(finance, ai_actions.brief, "Person", person)
		self.assertNotIn("is_lapsed_giver", json.loads(data_of(call))["summary"])
		self.assertEqual(call.kwargs["sends"], ("Person",))

	def test_a_brief_writes_one_access_log_row_and_saves_nothing(self):
		person = self.make_visited("Logged")
		modified = frappe.db.get_value("Person", person, "modified")
		filters = {"user": self.staff, "method": ai.PERSON_BRIEFING, "reference_document": person}
		pop_logs("Access Log", filters)

		run_action(self.staff, ai_actions.brief, "Person", person)

		self.assertEqual(len(pop_logs("Access Log", filters)), 1)
		self.assertEqual(frappe.db.get_value("Person", person, "modified"), modified)

	def test_a_group_brief_sends_its_members(self):
		member = make_person("Member", LAST_NAME, church=self.branch_a).name
		group = {"doctype": "Group", "group_name": "_Test AI Brief Group", "church": self.branch_a}
		group = frappe.get_doc({**group, "members": [{"person": member}]}).insert(ignore_permissions=True)

		_result, call = run_action(self.staff, ai_actions.brief, "Group", group.name)

		self.assertEqual(call.kwargs["sends"], ("Group", "Person"))
		self.assertIn(f"Member {LAST_NAME}", data_of(call))

	def test_only_a_person_or_a_group_is_briefed(self):
		family = {"doctype": "Family", "family_name": "_Test AI Brief", "church": self.branch_a}
		family = frappe.get_doc(family).insert(ignore_permissions=True).name

		self.assertRaises(
			frappe.ValidationError, run_action, self.manager, ai_actions.brief, "Family", family
		)

	def test_the_check_keeps_the_summary_as_text(self):
		self.assertEqual(
			ai_actions.check_brief({"summary": " Joined in May. "}), {"summary": "Joined in May."}
		)
		self.assertRaises(frappe.ValidationError, ai_actions.check_brief, {"summary": ""})


class TestDraftNote(ActionTestCase):
	def test_a_note_draft_offers_only_the_categories_the_caller_may_add(self):
		person = make_person("Noted", LAST_NAME, church=self.branch_a).name
		make_category("_Test AI Finance Notes", create_roles=["Church Finance"])
		make_category("_Test AI Open Notes")

		_result, call = run_action(self.manager, ai_actions.draft_note, person, "Called her. Doing well.")

		prompt = prompt_of(call)
		self.assertIn("_Test AI Open Notes", prompt)
		self.assertNotIn("_Test AI Finance Notes", prompt)
		self.assertNotIn(f"Noted {LAST_NAME}", prompt)
		self.assertIn("Called her. Doing well.", data_of(call))
		self.assertIn('Shape: {"category": "...", "contact_method": "...", "noted_on": "YYYY-MM-DD"', prompt)
		self.assertEqual(call.kwargs["sends"], ("Person Note",))
		self.assertEqual(call.kwargs["check"], ai_actions.NOTE_DRAFTS["Person Note"]["check"])

	def test_the_check_drops_what_the_caller_could_not_choose(self):
		make_category("_Test AI Finance Notes", create_roles=["Church Finance"])
		answer = {
			"category": "_Test AI Finance Notes",
			"contact_method": "Carrier Pigeon",
			"noted_on": "2026-11-02",
			"note": "Asked for prayer.\n<img src=https://example.com/x.png>",
		}

		result = as_user(self.manager, ai_actions.check_person_note, answer)

		self.assertEqual(
			result["values"],
			{
				"noted_on": "2026-11-02",
				"note": "<p>Asked for prayer.</p><p>&lt;img src=https://example.com/x.png&gt;</p>",
			},
		)

	def test_a_visit_draft_takes_listed_values_and_whole_minutes(self):
		visit_type = ensure("Visit Type", {"type": "_Test AI Hospital"})
		answer = {
			"visit_type": visit_type,
			"visit_date": "next Tuesday",
			"status": "Completed",
			"duration_minutes": "an hour",
			"follow_up_needed": True,
			"notes": "Prayed together.",
		}

		result = as_user(self.care, ai_actions.check_visitation_log, answer)

		self.assertEqual(
			result["values"],
			{
				"visit_type": visit_type,
				"status": "Completed",
				"follow_up_needed": 1,
				"notes": "<p>Prayed together.</p>",
			},
		)

	def test_a_note_is_logged_on_the_person_and_saved_only_from_the_form(self):
		person = make_person("Drafted", LAST_NAME, church=self.branch_a).name
		filters = {"user": self.manager, "method": "AI: Note draft", "reference_document": person}
		pop_logs("Access Log", filters)

		run_action(self.manager, ai_actions.draft_note, person, "Visited at home.")
		values = as_user(self.manager, ai_actions.check_person_note, {"note": "Visited at home."})["values"]
		link = as_user(self.manager, drafts.propose, "Person Note", {**values, "person": person})

		self.assertEqual(len(pop_logs("Access Log", filters)), 1)
		self.assertFalse(frappe.db.exists("Person Note", {"person": person}))
		token = link["url"].split("ai_draft=")[1]
		draft = as_user(self.manager, drafts.get_draft, token)
		self.assertEqual(draft["values"]["person"], person)

	def test_a_user_who_may_not_add_the_record_is_refused(self):
		person = make_person("Refused", LAST_NAME, church=self.branch_a).name

		self.assertRaises(
			frappe.PermissionError,
			run_action,
			self.staff,
			ai_actions.draft_note,
			person,
			"Visited.",
			"Visitation Log",
		)


class TestImportMapping(ActionTestCase):
	CSV = "First Name,Cell Phone,Shoe Size\nAnn Quillfeather,555-0199,Size Eleven\n"

	def make_import(self, user, reference_doctype="People Import"):
		frappe.set_user(user)
		try:
			data_import = {
				"doctype": "Data Import",
				"reference_doctype": reference_doctype,
				"import_type": INSERT,
			}
			data_import = frappe.get_doc(data_import).insert()
			file = {
				"doctype": "File",
				"file_name": f"_test_ai_mapping_{frappe.generate_hash(length=8)}.csv",
				"content": self.CSV,
				"is_private": 1,
				"attached_to_doctype": "Data Import",
				"attached_to_name": data_import.name,
				"attached_to_field": "import_file",
			}
			data_import.db_set("import_file", frappe.get_doc(file).insert().file_url)
			return data_import.name
		finally:
			frappe.set_user("Administrator")

	def test_only_the_unknown_headings_go_to_the_ai(self):
		data_import = self.make_import(self.manager)

		_result, call = run_action(self.manager, ai_actions.suggest_import_mapping, data_import)

		self.assertEqual(data_of(call), "1: Cell Phone\n2: Shoe Size")
		for value in ("Quillfeather", "555-0199", "Size Eleven"):
			self.assertNotIn(value, prompt_of(call))
		self.assertIn('"mobile_phone": "Mobile Phone"', prompt_of(call))
		self.assertEqual(call.kwargs.get("sends", ()), ())

	def test_another_users_import_and_an_import_of_records_are_refused(self):
		manager_b = ensure_user("_test_ai_actions_manager_b@example.com", "AI B", ["Church Manager"])
		set_user_church(manager_b, self.branch_b)
		theirs = self.make_import(manager_b)
		people = self.make_import(self.manager, "Person")

		self.assertRaises(
			frappe.PermissionError, run_action, self.manager, ai_actions.suggest_import_mapping, theirs
		)
		self.assertRaises(
			frappe.ValidationError, run_action, self.manager, ai_actions.suggest_import_mapping, people
		)

	def test_the_check_keeps_fields_of_the_named_import_once(self):
		answer = {
			"import": "People Import",
			"mapping": [
				{"column": 1, "field": "mobile_phone"},
				{"column": 2, "field": "shoe_size"},
				{"column": "x", "field": "nickname"},
				{"column": 3, "field": "mobile_phone"},
			],
		}

		result = as_user(self.manager, ai_actions.check_import_mapping, answer)

		self.assertEqual(result, {"import": "People Import", "mapping": {"1": "mobile_phone"}})
		for wrong in ({**answer, "import": "ToDo"}, {"import": "People Import", "mapping": []}):
			self.assertRaises(
				frappe.ValidationError, as_user, self.manager, ai_actions.check_import_mapping, wrong
			)

	def test_the_desk_script_offers_the_mapping_on_churchits_imports(self):
		script = Path(frappe.get_app_path("churchit", "public", "js", "ai_people.js")).read_text()
		listed = re.search(r"const IMPORTS = \[(.*?)\];", script, re.DOTALL).group(1)

		self.assertEqual(set(re.findall(r'"([^"]+)"', listed)), ai_actions.get_import_doctypes())


class TestTheAgentOnFlow(FlowRunnerTestCase):
	"""Each action reaches the agent its records need, with Flow's session patched. Needs Flow."""

	def run_as_staff(self, function, *args) -> str:
		"""The churchit agent that *function* runs as STAFF."""
		frappe.set_user(STAFF)
		with flow_session() as new_session:
			function(*args)
		self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")
		return new_session.call_args.args[0].name

	def make_staff_person(self, first_name: str) -> str:
		church_a = make_two_churches()[1]
		return make_person(first_name, LAST_NAME, church=church_a).name

	def test_a_note_needs_a_zero_retention_or_local_model(self):
		person = self.make_staff_person("Flow Noted")
		make_category("_Test AI Flow Notes")

		self.set_labels("Local", "No training")
		self.assertRaises(frappe.PermissionError, self.run_as_staff, ai_actions.draft_note, person, "Called.")
		self.set_labels("May train", "Zero retention")
		self.assertEqual(self.run_as_staff(ai_actions.draft_note, person, "Called."), PRIVATE_WORK)

	def test_a_description_runs_on_any_label_and_a_brief_needs_no_training(self):
		person = self.make_staff_person("Flow Briefed")

		self.set_labels("May train", "May train")
		self.assertEqual(self.run_as_staff(ai_actions.describe_people, "members in a group"), WRITER)
		self.assertRaises(frappe.PermissionError, self.run_as_staff, ai_actions.brief, "Person", person)
		self.set_labels("No training", "May train")
		self.assertEqual(self.run_as_staff(ai_actions.brief, "Person", person), WRITER)
