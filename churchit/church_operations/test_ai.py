# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Action items from Meeting Minutes: a Church Manager's own minutes, sent as Private Work, back as
Church Task drafts that nobody saved. runner.start is patched; tests never call a model."""

from unittest.mock import patch

import frappe

from churchit.ai import drafts, runner
from churchit.ai.test_runner import PRIVATE_WORK, FlowRunnerTestCase, flow_session
from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations import ai
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.church_people.test_ai_actions import data_of, prompt_of, run_action
from churchit.tests.helpers import ensure_user, make_two_churches, pop_logs

MINUTES = "<p>Ruth will order the new hymnals by 2026-12-01.</p><p>Paul to fix the leaking roof.</p>"


def make_minutes(church, minutes=MINUTES):
	return (
		frappe.get_doc(
			{
				"doctype": "Meeting Minutes",
				"title": "_Test AI Board Meeting",
				"meeting_date": "2026-11-05",
				"church": church,
				"minutes": minutes,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestActionItems(AITestCase):
	def test_only_a_church_manager_of_the_minutes_church_may_ask(self):
		mine, theirs = make_minutes(self.branch_a), make_minutes(self.branch_b)

		for user, minutes in ((self.staff, mine), (self.member, mine), (self.manager, theirs)):
			with self.subTest(user=user, minutes=minutes):
				self.assertRaises(frappe.PermissionError, run_action, user, ai.action_items, minutes)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, run_action, self.manager, ai.action_items, mine)

	def test_the_minutes_go_as_private_work_and_are_logged(self):
		minutes = make_minutes(self.branch_a)
		filters = {"user": self.manager, "method": "AI: Action items", "reference_document": minutes}
		pop_logs("Access Log", filters)

		_result, call = run_action(self.manager, ai.action_items, minutes)

		self.assertEqual(call.kwargs["sends"], ("Meeting Minutes",))
		self.assertEqual(call.kwargs["reference_name"], minutes)
		self.assertIn("Paul to fix the leaking roof.", data_of(call))
		self.assertNotIn("<p>", data_of(call))
		self.assertIn("2026-11-05", prompt_of(call))
		self.assertEqual(len(pop_logs("Access Log", filters)), 1)

	def test_minutes_without_text_are_refused(self):
		minutes = make_minutes(self.branch_a, minutes="<p></p>")

		self.assertRaises(frappe.ValidationError, run_action, self.manager, ai.action_items, minutes)

	def test_each_task_opens_as_a_draft_and_none_is_saved(self):
		answer = {
			"tasks": [
				{
					"title": "Order the new hymnals",
					"owner": "Ruth",
					"due_date": "2026-12-01",
					"priority": "High",
				},
				{"title": "Fix the roof", "owner": "Paul", "due_date": "soon", "priority": "Whenever"},
				{"owner": "Nobody"},
			]
		}
		before = frappe.db.count("Church Task")

		tasks = as_user(self.manager, ai.check_action_items, answer)["tasks"]

		self.assertEqual(frappe.db.count("Church Task"), before)
		self.assertEqual([task["owner"] for task in tasks], ["Ruth", "Paul"])
		first = as_user(self.manager, drafts.get_draft, tasks[0]["url"].split("ai_draft=")[1])
		second = as_user(self.manager, drafts.get_draft, tasks[1]["url"].split("ai_draft=")[1])
		self.assertEqual(
			first["values"],
			{"title": "Order the new hymnals", "due_date": "2026-12-01 00:00:00", "priority": "High"},
		)
		self.assertEqual(second["values"], {"title": "Fix the roof"})

	def test_an_answer_without_tasks_is_refused(self):
		for answer in ({"tasks": []}, {"tasks": [{"title": ""}]}, {"items": "none"}):
			with self.subTest(answer=answer):
				self.assertRaises(
					frappe.ValidationError, as_user, self.manager, ai.check_action_items, answer
				)


class TestActionItemsOnFlow(FlowRunnerTestCase):
	"""Meeting Minutes are private records, so only a Zero retention or Local model gets them. Needs Flow."""

	def run_as(self, user: str, minutes: str) -> str:
		"""The churchit agent that action_items runs as *user*, with Flow's session patched."""
		frappe.set_user(user)
		with flow_session() as new_session:
			ai.action_items(minutes)
		self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")
		return new_session.call_args.args[0].name

	def test_the_minutes_need_a_zero_retention_or_local_model(self):
		church_a = make_two_churches()[1]
		manager = ensure_user(
			"_test_ai_minutes_manager@example.com", "AI Minutes", ["Church Manager", "Flow User"]
		)
		set_user_church(manager, church_a)
		minutes = make_minutes(church_a)

		self.set_labels("Local", "No training")
		self.assertRaises(frappe.PermissionError, self.run_as, manager, minutes)
		self.set_labels("No training", "Local")
		self.assertEqual(self.run_as(manager, minutes), PRIVATE_WORK)
