# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Forms and follow-up workflows from a sentence: what each prompt holds and the unsaved drafts."""

from unittest import mock
from urllib.parse import parse_qs, urlparse

import frappe

from churchit import questions
from churchit.ai.drafts import get_draft
from churchit.ai.switch import SETTINGS
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	create_communication_purposes,
)
from churchit.church_foundations.church_access import set_user_church
from churchit.church_setup import ai
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_two_churches

MANAGER = "_test_setup_ai_manager@example.com"
STAFF = "_test_setup_ai_staff@example.com"
START = "churchit.ai.runner.start"
TEMPLATE = "_Test Setup AI Welcome"
INTEREST = "_Test Setup AI Interest"


def get_values(result: dict) -> dict:
	"""The values of the draft that a check made, as the form gets them."""
	token = parse_qs(urlparse(result["url"]).query)["ai_draft"][0]
	return get_draft(token)["values"]


class SetupTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, _other = make_two_churches()
		for user, roles in ((MANAGER, ("Church Manager",)), (STAFF, ("Church Staff",))):
			ensure_user(user, "Setup AI", roles)
			set_user_church(user, cls.church)
		create_communication_purposes()
		ensure(
			"Email Template",
			{"name": TEMPLATE},
			{"name": TEMPLATE, "subject": "Welcome", "response": "Hello {{ first_name }}"},
		)
		ensure("Connection Card Interest", {"interest": INTEREST})
		cls.purpose = frappe.get_all("Communication Purpose", pluck="name", limit=1)[0]

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, "enabled", 1)
		frappe.set_user(MANAGER)

	def start(self, function, description: str) -> mock.MagicMock:
		with mock.patch(START, return_value={"token": "t"}) as start:
			self.assertEqual(function(description), {"token": "t"})
		return start


class TestQuestionSet(SetupTestCase):
	def test_a_description_starts_a_writer_run_without_church_records(self):
		start = self.start(ai.draft_question_set, "A retreat sign-up with T-shirt sizes")

		prompt = start.call_args.args[1]
		self.assertNotIn("sends", start.call_args.kwargs)
		self.assertIs(frappe.get_attr(start.call_args.kwargs["check"]), ai.check_question_set)
		self.assertTrue(
			prompt.endswith("The staff member asks for this form: A retreat sign-up with T-shirt sizes")
		)
		for answer_type in questions.FIELDS:
			self.assertIn(f"- {answer_type}: ", prompt)

	def test_a_reader_who_cannot_create_one_or_an_empty_description_is_refused(self):
		with mock.patch(START) as start:
			with self.assertRaises(frappe.ValidationError):
				ai.draft_question_set(" ")
			frappe.set_user(STAFF)
			with self.assertRaises(frappe.PermissionError):
				ai.draft_question_set("A form")
		start.assert_not_called()

	def test_the_answer_opens_an_unsaved_question_set(self):
		before = frappe.db.count(ai.QUESTION_SET)
		answer = {
			"title": "Retreat",
			"questions": [
				{"label": "T-shirt size?", "type": "Select", "required": True, "choices": ["S", "M", ""]},
				{"label": "Allergies", "type": "Small Text", "fieldname": "evil_name"},
				{"label": " ", "type": "Data"},
				{"label": "Your verse (Mark 16:21)", "type": "Data"},
			],
		}
		result = ai.check_question_set(answer)

		rows = get_values(result)["questions"]
		self.assertEqual(frappe.db.count(ai.QUESTION_SET), before)
		self.assertEqual([row["fieldname"] for row in rows], ["t_shirt_size", "allergies"])
		self.assertEqual(rows[0]["options"], "S\nM")
		self.assertEqual([row["is_required"] for row in rows], [1, 0])
		self.assertEqual(result["questions"][1]["question_type"], "Small Text")

	def test_an_answer_type_a_question_set_lacks_is_refused(self):
		for kind in ("Unsupported", "Conditional", "Attach", ["Data"]):
			answer = {"title": "x", "questions": [{"label": "Upload", "type": kind}]}
			with self.assertRaisesRegex(frappe.ValidationError, "A Question Set asks only"):
				ai.check_question_set(answer)


class TestFollowupWorkflow(SetupTestCase):
	def test_the_prompt_offers_only_the_names_the_caller_may_read(self):
		start = self.start(ai.draft_followup_workflow, "Welcome first-time guests")
		prompt = start.call_args.args[1]

		self.assertIs(frappe.get_attr(start.call_args.kwargs["check"]), ai.check_followup_workflow)
		self.assertIn(TEMPLATE, prompt)
		self.assertIn(INTEREST, prompt)
		self.assertIn("Send Email, Send Text, Add to Group, Add Tag", prompt)
		self.assertIn("{{ step }}", prompt)
		self.assertIn("The staff member describes the process: Welcome first-time guests", prompt)
		names = prompt.split('<data source="names">')[1]
		self.assertIn(TEMPLATE, names)
		interests = next(line for line in names.splitlines() if line.startswith("Connection Card value: "))
		self.assertIn(INTEREST, interests)

	def test_the_answer_opens_an_unsaved_workflow_without_what_it_cannot_do(self):
		answer = {
			"workflow_name": "Welcome",
			"steps": [
				{"step": "Call", "due_in_days": 2},
				{"step": "Visit", "due_in_days": -4},
				{"step": "Call"},
			],
			"triggers": [
				{"trigger": "Connection Card", "value": INTEREST.upper()},
				{"trigger": "Birthday"},
				{"trigger": ["Connection Card"]},
			],
			"actions": [
				{
					"run_on": "Card Opened",
					"action": "Send Email",
					"purpose": self.purpose,
					"email_template": TEMPLATE,
				},
				{
					"run_on": "Step Reached",
					"step": "Visit",
					"action": "Send Text",
					"purpose": self.purpose,
					"message": "Hi {{ first_name }}, at {{ step }}",
				},
				{"run_on": "Card Opened", "action": "Send Fax"},
				{"run_on": "Card Opened", "action": "Send Text", "message": "Hi {{ frappe.db }}"},
				{"run_on": "Card Opened", "action": "Add to Group", "group": "_Test No Such Group"},
			],
		}
		result = ai.check_followup_workflow(answer)

		values = get_values(result)
		self.assertEqual(values["is_active"], 0)
		self.assertEqual(result["left_out"], 4)
		self.assertEqual(
			[(row["step"], row["due_in_days"]) for row in values["steps"]], [("Call", 2), ("Visit", 0)]
		)
		self.assertEqual(values["triggers"], [{"trigger": "Connection Card", "value": INTEREST}])
		self.assertEqual(values["actions"][0]["email_template"], TEMPLATE)
		self.assertEqual(values["actions"][1]["step"], "Visit")
		self.assertEqual(values["actions"][2], {"run_on": "Card Opened", "action": "Add to Group"})
		self.assertFalse(frappe.db.exists(ai.WORKFLOW, "Welcome"))

	def test_an_answer_without_steps_cannot_be_used(self):
		for answer in ([], {"steps": []}, {"steps": [{"step": " "}]}):
			with self.assertRaisesRegex(frappe.ValidationError, "The AI answer could not be used."):
				ai.check_followup_workflow(answer)
