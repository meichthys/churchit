# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The weekly AI note: only its user turns it on, it sends numbers only and no giving, as that user,
without the churches that keep away, and it arrives as escaped text with churchit's own links.

Tests never call a model: runner.start is patched, or Flow's session on a Flow bench, and delivery
gets a fake Flow Run.
"""

import json
import re
import unittest
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.cache_manager import clear_defaults_cache
from frappe.permissions import add_user_permission
from frappe.utils import get_url_to_list, getdate, today

from churchit.ai import runner
from churchit.ai.flow_models import WRITER
from churchit.ai.test_runner import STAFF, FlowRunnerTestCase, fake_run, flow_session
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import add_card
from churchit.church_people.test_ai import as_user, set_ai
from churchit.church_summary import ai as summary
from churchit.church_summary.metrics import save_row
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

DATA_BLOCK = re.compile(r"<data[^>]*>\n(.*)\n</data>", re.DOTALL)
NOTICE = "Notification Log"
GIVING = {"giving_total": 98765.43, "givers": 4321}


def get_numbers(start) -> dict:
	"""The numbers that the note's prompt sent."""
	return json.loads(DATA_BLOCK.search(start.call_args.args[1]).group(1))


def read_app_json(*path: str):
	return frappe.get_file_json(frappe.get_app_path("churchit", *path))


def notices_for(user: str) -> list[dict]:
	return frappe.get_all(NOTICE, filters={"for_user": user}, fields=["type", "subject", "email_content"])


class WeeklyNoteTestCase(RollbackEachTest):
	"""Two branches with last week's figures; Church Staff of each, and a finance user of branch A."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.staff = ensure_user("_test_note_staff@example.com", "Note Staff", ["Church Staff"])
		cls.finance = ensure_user(
			"_test_note_finance@example.com", "Note Finance", ["Church Staff", "Church Finance"]
		)
		cls.other = ensure_user("_test_note_other@example.com", "Note Other", ["Church Staff"])
		cls.member = ensure_user("_test_note_member@example.com", "Note Member", ["Church User"])
		cls.manager = ensure_user("_test_note_manager@example.com", "Note Manager", ["Church Manager"])
		for user in (cls.staff, cls.finance, cls.member, cls.manager):
			set_user_church(user, cls.branch_a)
		set_user_church(cls.other, cls.branch_b)
		cls.prayer_type = ensure("Prayer Request Type", {"type": "Health"})
		ensure("Prayer Request Status", {"status": summary.WAITING_STATUS})

	def setUp(self):
		super().setUp()
		set_ai(1)
		day = getdate(today())
		last_monday = day - timedelta(days=day.weekday() + 7)
		figures = {self.branch_a: (123, 7, 41), self.branch_b: (777, 55, 66)}
		for church, (attendance, visitors, serving) in figures.items():
			values = {"attendance": attendance, "first_time_visitors": visitors, "people_serving": serving}
			save_row(church, last_monday, {**values, **GIVING})

	def opt_in(self, *users):
		for user in users:
			self.assertTrue(as_user(user, summary.set_weekly_note, 1))
			self.addCleanup(clear_defaults_cache, user)

	def run_note(self, user: str, agents=frozenset({WRITER})):
		"""run_weekly_note for *user* with Flow ready; the patched runner.start."""
		with ExitStack() as stack:
			stack.enter_context(patch.object(summary, "has_flow", return_value=True))
			stack.enter_context(patch.object(summary, "is_flow_ready", return_value=True))
			stack.enter_context(patch.object(runner, "get_usable_agents", return_value=set(agents)))
			start = stack.enter_context(patch.object(runner, "start", return_value={}))
			summary.run_weekly_note(user)
		self.assertEqual(frappe.session.user, "Administrator")
		return start

	def deliver(self, user: str, output: str) -> None:
		as_user(user, summary.deliver_weekly_note, fake_run(output=output))


class TestTurningTheNoteOn(WeeklyNoteTestCase):
	def test_you_turn_only_your_own_note_on_and_off(self):
		self.opt_in(self.staff)

		self.assertTrue(as_user(self.staff, summary.get_weekly_note))
		self.assertFalse(as_user(self.other, summary.get_weekly_note))
		owners = frappe.db.get_values(
			"DefaultValue", {"defkey": summary.NOTE_KEY, "defvalue": "1"}, "parent", pluck=True
		)
		self.assertIn(self.staff, owners)
		self.assertNotIn(self.other, owners)
		self.assertNotIn("__default", owners)
		self.assertFalse(as_user(self.staff, summary.set_weekly_note, 0))
		self.assertFalse(as_user(self.staff, summary.get_weekly_note))

	def test_a_portal_member_and_ai_off_are_refused(self):
		self.assertRaises(frappe.PermissionError, as_user, self.member, summary.set_weekly_note, 1)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, as_user, self.staff, summary.set_weekly_note, 1)
		self.assertRaises(frappe.PermissionError, as_user, self.staff, summary.get_weekly_note)


class TestTheMondayJobs(WeeklyNoteTestCase):
	def queued(self) -> dict[str, dict]:
		with (
			patch.object(summary, "has_flow", return_value=True),
			patch("churchit.church_summary.ai.frappe.enqueue") as enqueue,
		):
			summary.queue_weekly_notes()
		return {call.kwargs["user"]: call for call in enqueue.call_args_list}

	def test_one_job_for_each_opted_in_enabled_desk_user(self):
		disabled = ensure_user("_test_note_disabled@example.com", "Note Disabled", ["Church Staff"])
		self.opt_in(self.staff, self.other, disabled)
		frappe.db.set_value("User", disabled, "enabled", 0)
		frappe.defaults.set_user_default(summary.NOTE_KEY, "1", user=self.member)
		self.addCleanup(clear_defaults_cache, self.member)

		jobs = self.queued()

		self.assertLessEqual({self.staff, self.other}, set(jobs))
		self.assertFalse({disabled, self.member} & set(jobs))
		call = jobs[self.staff]
		self.assertEqual(call.args, (summary.NOTE_JOB,))
		self.assertEqual(call.kwargs["job_id"], f"ai-weekly-note:{self.staff}")
		self.assertTrue(call.kwargs["deduplicate"])
		self.assertEqual(call.kwargs["queue"], "long")

	def test_ai_off_stops_the_next_note(self):
		self.opt_in(self.staff)
		set_ai(0)

		self.assertEqual(self.queued(), {})
		self.run_note(self.staff).assert_not_called()
		before = len(notices_for(self.staff))
		self.deliver(self.staff, json.dumps({"sentences": ["Attendance rose."]}))
		self.assertEqual(len(notices_for(self.staff)), before)

	def test_a_user_who_cannot_use_writer_or_turned_the_note_off_gets_no_run(self):
		self.run_note(self.staff).assert_not_called()
		self.opt_in(self.staff)
		self.run_note(self.staff, agents=()).assert_not_called()
		self.run_note(self.staff).assert_called_once()


class TestTheNumbers(WeeklyNoteTestCase):
	def test_a_staff_note_holds_only_numbers_of_their_church_and_no_giving(self):
		self.opt_in(self.staff, self.finance)

		for user in (self.staff, self.finance):
			start = self.run_note(user)
			prompt = start.call_args.args[1]
			[week] = [week for week in get_numbers(start)["weeks"] if week["attendance"]]
			self.assertEqual(week["attendance"], 123)
			self.assertEqual((week["first_time_visitors"], week["people_serving"]), (7, 41))
			self.assertEqual(set(week), {"week_start", *summary.NOTE_METRICS})
			for figure in ("98765", "4321", "777"):
				self.assertNotIn(figure, prompt)
			self.assertEqual(start.call_args.kwargs, {"deliver": summary.DELIVER_NOTE})
			self.assertEqual(start.call_args.args[0], summary.WEEKLY_NOTE)

	def test_one_users_job_never_reads_another_users_numbers(self):
		self.opt_in(self.staff, self.other)
		workflow = make_workflow("_Test Note Calls", [("Call", self.staff, 0)], church=self.branch_a).name
		add_card(make_person("Noted", "_Test Note", church=self.branch_a).name, workflow)

		mine = get_numbers(self.run_note(self.staff))
		theirs = get_numbers(self.run_note(self.other))
		again = get_numbers(self.run_note(self.staff))

		self.assertEqual([week["attendance"] for week in mine["weeks"] if week["attendance"]], [123])
		self.assertEqual([week["attendance"] for week in theirs["weeks"] if week["attendance"]], [777])
		self.assertEqual((mine["my_open_follow_ups"], theirs["my_open_follow_ups"]), (1, 0))
		self.assertEqual(again, mine)

	def test_the_churches_that_keep_away_are_left_out(self):
		self.opt_in(self.staff, self.other)
		add_user_permission("Church", self.branch_b, self.staff, ignore_permissions=True)

		def attendance():
			numbers = get_numbers(self.run_note(self.staff))
			return sum(week["attendance"] for week in numbers["weeks"])

		self.assertEqual(attendance(), 900)
		frappe.db.set_value("Church", self.branch_b, "keep_away_from_ai", 1)
		self.assertEqual(attendance(), 123)
		self.run_note(self.other).assert_not_called()

	def test_prayer_requests_waiting_are_those_the_user_reads_and_none_private(self):
		self.opt_in(self.manager)
		before = get_numbers(self.run_note(self.manager))["prayer_requests_waiting"]
		for church, visibility in (
			(self.branch_a, "Whole Church"),
			(self.branch_a, "Private"),
			(self.branch_b, "Whole Church"),
		):
			frappe.get_doc(
				{
					"doctype": "Prayer Request",
					"title": "_Test Note Prayer",
					"type": self.prayer_type,
					"church": church,
					"visibility": visibility,
				}
			).insert(ignore_permissions=True)

		self.assertEqual(get_numbers(self.run_note(self.manager))["prayer_requests_waiting"], before + 1)


class TestDelivery(WeeklyNoteTestCase):
	def test_the_note_arrives_to_its_user_only_as_text_with_churchits_links(self):
		self.opt_in(self.staff)
		others = len(notices_for(self.other))
		sentences = [
			'Attendance rose. <img src="x" onerror="alert(1)">',
			'Read <a href="https://evil.example/a">this</a> or https://evil.example/b today.',
		]

		self.deliver(self.staff, json.dumps({"sentences": sentences}))

		[notice] = notices_for(self.staff)
		self.assertEqual(notice.type, "Alert")
		self.assertIn("&lt;img", notice.email_content)
		self.assertNotIn("<img", notice.email_content)
		self.assertNotIn("evil.example", notice.email_content)
		self.assertIn(f'href="{get_url_to_list("Weekly Metrics")}"', notice.email_content)
		self.assertEqual(len(notices_for(self.other)), others)

	def test_an_unusable_answer_or_a_note_turned_off_leaves_nothing(self):
		self.opt_in(self.staff)
		self.deliver(self.staff, "not json")
		self.deliver(self.staff, json.dumps({"sentences": []}))
		as_user(self.staff, summary.set_weekly_note, 0)
		self.deliver(self.staff, json.dumps({"sentences": ["Attendance rose."]}))

		self.assertEqual(notices_for(self.staff), [])

	def test_the_check_keeps_at_most_five_one_line_sentences(self):
		answer = {"sentences": [f"Line\n{number}" for number in range(8)] + [3, " "]}
		self.assertEqual(summary.check_note(answer), [f"Line {number}" for number in range(5)])
		self.assertRaises(frappe.ValidationError, summary.check_note, {"note": "Attendance rose."})


class TestTheToggle(unittest.TestCase):
	def test_the_summary_workspace_shows_the_toggle_that_calls_the_note_methods(self):
		workspace = read_app_json("church_summary", "workspace", "summary", "summary.json")
		blocks = json.loads(workspace["content"])
		self.assertIn("WeeklyAINote", [block["data"].get("custom_block_name") for block in blocks])
		self.assertIn("WeeklyAINote", [row["custom_block_name"] for row in workspace["custom_blocks"]])
		[block] = [
			block
			for block in read_app_json("fixtures", "custom_html_block.json")
			if block["name"] == "WeeklyAINote"
		]
		for method in ("get_weekly_note", "set_weekly_note"):
			self.assertIn(f".{method}`", block["script"])
			self.assertIn(getattr(summary, method), frappe.whitelisted)


class TestOnFlow(FlowRunnerTestCase):
	def test_a_note_runs_on_writer_whatever_its_label_and_names_its_delivery(self):
		self.set_labels("May train", "May train")
		frappe.set_user(STAFF)
		summary.set_weekly_note(1)
		self.addCleanup(clear_defaults_cache, STAFF)
		frappe.set_user("Administrator")

		with flow_session() as new_session:
			summary.run_weekly_note(STAFF)

		self.assertEqual(new_session.call_args.args[0].name, "churchit/Writer")
		self.assertEqual(new_session.call_args.kwargs, {"title": summary.WEEKLY_NOTE})
		self.assertEqual(new_session.return_value.chat.call_args.kwargs["on_complete"], summary.DELIVER_NOTE)
