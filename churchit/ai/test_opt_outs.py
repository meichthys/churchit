# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A church that keeps away from churchit's AI and a person who keeps their details out of it: what
churchit's own AI features leave out, what they refuse and who sees their buttons.

runner.start is patched, so no test calls a model; the boot test needs Flow and skips without it.
"""

import json
from unittest.mock import patch

import frappe
from frappe.utils import today

from churchit.ai import opt_outs, reports, writing
from churchit.ai.switch import extend_bootinfo
from churchit.ai.test_runner import STAFF, FlowRunnerTestCase, staff_user
from churchit.ai.test_triage import TriageFlowCase
from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations import ai as operations_ai
from churchit.church_people import ai_actions
from churchit.church_people.followup import CARD
from churchit.church_people.test_ai import AITestCase, as_user
from churchit.church_people.test_ai_actions import data_of, run_action
from churchit.church_scope import root_church
from churchit.church_study import ai as study_ai
from churchit.tests.helpers import ensure_user, make_person, make_two_churches

LAST_NAME = "_Test Opt Outs"
MANAGER_B = "_test_opt_outs_manager_b@example.com"
STAFF_B = "_test_opt_outs_staff_b@example.com"
MANAGER_ALL = "_test_opt_outs_manager_all@example.com"


def keep_away(church: str, value: int = 1) -> None:
	frappe.db.set_value("Church", church, opt_outs.CHURCH_FIELD, value)


def record(doctype: str, **values) -> str:
	"""A bare record of *doctype*, without its hooks: only its links matter here."""
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.db_insert()
	return doc.name


class OptOutTestCase(AITestCase):
	"""Branch B keeps away from AI. In branch A, Kept In uses AI and Left Out keeps their details out."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_user(MANAGER_B, "Opt Out Manager", ["Church Manager"])
		set_user_church(MANAGER_B, cls.branch_b)

	def setUp(self):
		super().setUp()
		keep_away(self.branch_b)
		self.kept_in = make_person("Kept In", LAST_NAME, church=self.branch_a).name
		self.left_out = make_person("Left Out", LAST_NAME, church=self.branch_a, exclude_from_ai=1).name
		self.of_b = make_person("Branch B", LAST_NAME, church=self.branch_b).name

	def refused(self, user: str, function, *args, **kwargs):
		"""Assert that *function* refuses with the opt-out sentence and starts no run."""
		with self.assertRaisesRegex(frappe.PermissionError, "leave this record out"):
			run_action(user, function, *args, **kwargs)


class TestWhatIsKeptAway(OptOutTestCase):
	def test_a_person_who_keeps_out_and_every_person_of_a_church_that_keeps_away(self):
		people = [self.kept_in, self.left_out, self.of_b]

		self.assertEqual(opt_outs.get_kept_away("Person", people), {self.left_out, self.of_b})
		self.assertTrue(opt_outs.is_kept_away("Church", self.branch_b))
		self.assertFalse(opt_outs.is_kept_away("Church", self.branch_a))

		keep_away(self.branch_b, 0)
		self.assertEqual(opt_outs.get_kept_away("Person", people), {self.left_out})

	def test_a_request_of_such_a_church_or_about_such_a_person_is_kept_away(self):
		"""The records that suggestions on new requests read (churchit.ai.triage)."""
		prayer = {"doctype": "Prayer Request", "title": "Pray", "church": self.branch_a}
		requests = {
			record(**prayer, requestor=self.kept_in): False,
			record(**{**prayer, "church": self.branch_b}, requestor=self.kept_in): True,
			record(**prayer, requestor=self.left_out): True,
			record(**prayer, requestor=self.kept_in, recipient_type="Person", recipient=self.of_b): True,
			record(**prayer, requestor=self.kept_in, recipient_type="Group", recipient=self.of_b): False,
		}
		self.assertEqual(
			opt_outs.get_kept_away("Prayer Request", requests),
			{name for name, kept in requests.items() if kept},
		)

		care = record("Care Request", person=self.of_b, church=self.branch_a, description="Meals")
		card = record(CARD, person=self.left_out, church=self.branch_a, status="Open")
		other_card = record(CARD, person=self.kept_in, church=self.branch_a, status="Open")
		self.assertTrue(opt_outs.is_kept_away("Care Request", care), "Its person's church keeps away")
		self.assertTrue(opt_outs.is_kept_away(CARD, card))
		self.assertFalse(opt_outs.is_kept_away(CARD, other_card))

	def test_a_shared_record_follows_the_church_that_shared_it(self):
		shared = {"doctype": "Meeting Minutes", "title": "Joint", "church": "", "is_shared": 1}
		minutes_b = record(**shared, shared_by_church=self.branch_b, meeting_date=today())
		minutes_a = record(**shared, shared_by_church=self.branch_a, meeting_date=today())

		self.assertEqual(opt_outs.get_kept_away("Meeting Minutes", [minutes_a, minutes_b]), {minutes_b})

	def test_a_record_without_a_church_is_the_only_churchs_on_a_single_church_site(self):
		minutes = record("Meeting Minutes", title="Board", church="", meeting_date=today())
		keep_away(root_church())

		self.assertFalse(opt_outs.is_kept_away("Meeting Minutes", minutes), "Several churches: it names none")
		with patch("churchit.ai.opt_outs.is_multi_church", return_value=False):
			self.assertTrue(opt_outs.is_kept_away("Meeting Minutes", minutes))

	def test_the_buttons_hide_only_for_a_user_whose_churches_all_keep_away(self):
		self.assertTrue(opt_outs.is_user_kept_away(MANAGER_B))
		self.assertFalse(opt_outs.is_user_kept_away(self.manager))
		self.assertFalse(opt_outs.is_user_kept_away("Administrator"), "Branch A and the root take AI")


class TestBriefMeAndNotes(OptOutTestCase):
	def test_a_brief_or_a_note_on_such_a_person_is_refused(self):
		for person in (self.left_out, self.of_b):
			with self.subTest(person):
				self.refused(self.manager, ai_actions.brief, "Person", person)
				self.refused(self.manager, ai_actions.draft_note, person, "Visited today.")

		_result, call = run_action(self.manager, ai_actions.brief, "Person", self.kept_in)
		self.assertIn(f"Kept In {LAST_NAME}", data_of(call))

	def test_a_group_brief_leaves_out_such_people(self):
		members = [{"person": person} for person in (self.kept_in, self.left_out, self.of_b)]
		group = {"doctype": "Group", "group_name": "_Test Opt Outs Group", "church": self.branch_a}
		group = frappe.get_doc({**group, "members": members}).insert(ignore_permissions=True).name

		_result, call = run_action(self.manager, ai_actions.brief, "Group", group)

		self.assertIn(f"Kept In {LAST_NAME}", data_of(call))
		self.assertNotIn("Left Out", data_of(call))
		self.assertNotIn("Branch B", data_of(call))

	def test_a_group_of_a_church_that_keeps_away_is_refused(self):
		group = {"doctype": "Group", "group_name": "_Test Opt Outs Group B", "church": self.branch_b}
		group = frappe.get_doc(group).insert(ignore_permissions=True).name

		self.refused(MANAGER_B, ai_actions.brief, "Group", group)

	def test_a_briefing_leaves_out_such_relatives_and_the_records_of_such_a_church(self):
		visit = {"person": self.kept_in, "visit_date": today()}
		visit_a = record("Visitation Log", **visit, church=self.branch_a)
		visit_b = record("Visitation Log", **visit, church=self.branch_b)
		card_b = record(CARD, person=self.kept_in, church=self.branch_b, status="Open")
		briefing = {
			"summary": {"full_name": "Kept In", "spouse": self.left_out},
			"household": [{"person": self.kept_in}, {"person": self.left_out}, {"person": self.of_b}],
			"open_follow_ups": [{"name": card_b}],
			"records": {
				"total": 2,
				"rows": [
					{"url": frappe.utils.get_url_to_form("Visitation Log", name)}
					for name in (visit_a, visit_b)
				],
			},
		}

		left = ai_actions.without_kept_away(briefing)

		self.assertEqual(left["summary"], {"full_name": "Kept In"})
		self.assertEqual(left["household"], [{"person": self.kept_in}])
		self.assertEqual(left["open_follow_ups"], [])
		self.assertEqual(left["records"]["rows"], [briefing["records"]["rows"][0]])


class TestExplain(OptOutTestCase):
	def explain(self, user: str, report_name: str, filters: dict):
		return run_action(user, reports.explain_report, report_name, json.dumps(filters))

	def test_the_rows_of_a_person_who_keeps_out_are_left_out(self):
		answer, call = self.explain(self.manager, "People", {"person_name": LAST_NAME})

		names = [row[0] for row in answer["rows"]]
		self.assertEqual(names, [f"Kept In {LAST_NAME}"])
		self.assertNotIn("Left Out", data_of(call))

	def test_a_row_that_names_such_a_person_or_church_in_a_link_is_left_out(self):
		columns = [
			{"fieldname": "person", "fieldtype": "Link", "options": "Person"},
			{"fieldname": "church", "fieldtype": "Link", "options": "Church"},
			{"fieldname": "count", "fieldtype": "Int"},
		]
		rows = [
			[self.kept_in, self.branch_a, 1],
			[self.left_out, self.branch_a, 2],
			{"person": self.kept_in, "church": self.branch_b, "count": 3},
			["Total", None, 6],
		]

		self.assertEqual(reports.without_kept_away("Group", columns, rows), [rows[0], rows[3]])

	def test_a_report_that_can_hold_rows_of_such_a_church_needs_a_church_filter_that_leaves_it_out(self):
		"""A total names no record but counts that church's records, so a reader of several churches picks one."""
		ensure_user(MANAGER_ALL, "Opt Out Manager All", ["Church Manager"])
		for name in frappe.get_all("User Permission", filters={"user": MANAGER_ALL}, pluck="name"):
			frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)

		with self.assertRaisesRegex(frappe.PermissionError, "pick a church"):
			self.explain(MANAGER_ALL, "People", {"person_name": LAST_NAME})
		answer, _call = self.explain(
			MANAGER_ALL, "People", {"person_name": LAST_NAME, "church": self.branch_a}
		)
		self.assertEqual([row[0] for row in answer["rows"]], [f"Kept In {LAST_NAME}"])
		with self.assertRaisesRegex(frappe.PermissionError, "pick a church"):
			self.explain(MANAGER_ALL, "Churches", {"church": self.branch_a})

	def test_filters_that_name_such_a_church_and_a_user_of_it_are_refused(self):
		with self.assertRaisesRegex(frappe.PermissionError, "filters name a church or a person"):
			self.explain(self.manager, "People", {"church": self.branch_b})
		with self.assertRaisesRegex(frappe.PermissionError, opt_outs.CHURCH_REFUSAL):
			self.explain(MANAGER_B, "People", {})


class TestOtherActions(OptOutTestCase):
	def test_draft_with_ai_action_items_and_study_helpers_refuse_a_record_of_such_a_church(self):
		group = {"doctype": "Group", "group_name": "_Test Opt Outs Draft", "church": self.branch_b}
		group_b = frappe.get_doc(group).insert(ignore_permissions=True).name
		minutes = {"doctype": "Meeting Minutes", "title": "Board", "meeting_date": today()}
		minutes_b = frappe.get_doc({**minutes, "church": self.branch_b, "minutes": "<p>Paint.</p>"})
		sermon_b = frappe.get_doc({"doctype": "Sermon", "title": "Grace", "church": self.branch_b})

		self.refused(MANAGER_B, writing.draft_text, "Group", "description", "write", group_b, "Welcome")
		self.refused(MANAGER_B, operations_ai.action_items, minutes_b.insert(ignore_permissions=True).name)
		self.refused(
			MANAGER_B, study_ai.study_helper, sermon_b.insert(ignore_permissions=True).name, "questions"
		)

		keep_away(self.branch_b, 0)
		_result, call = run_action(
			MANAGER_B, writing.draft_text, "Group", "description", "write", group_b, "Welcome"
		)
		self.assertIsNotNone(call, "A church that takes AI again gets its drafts")

	def test_draft_with_ai_on_a_new_record_of_such_a_church_is_refused(self):
		values = json.dumps({"church": self.branch_b})
		with self.assertRaisesRegex(frappe.PermissionError, "Your church keeps its records away"):
			run_action(
				MANAGER_B, writing.draft_text, "Group", "description", "write", None, "Welcome", None, values
			)

		keep_away(self.branch_b, 0)
		_result, call = run_action(
			MANAGER_B, writing.draft_text, "Group", "description", "write", None, "Welcome", None, values
		)
		self.assertIsNotNone(call)


class TestTheBoot(FlowRunnerTestCase):
	"""The desk hides churchit's AI buttons from a user whose churches all keep away. Needs Flow."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, _church_a, cls.church_b = make_two_churches()
		staff_user(STAFF_B, cls.church_b)

	def actions_of(self, user: str) -> tuple[bool, bool]:
		frappe.set_user(user)
		bootinfo = frappe._dict()
		extend_bootinfo(bootinfo)
		frappe.set_user("Administrator")
		return bootinfo.churchit["ai"]["actions"], bootinfo.churchit["ai"]["private_actions"]

	def test_a_user_of_a_church_that_keeps_away_sees_no_ai_buttons(self):
		self.assertEqual(self.actions_of(STAFF_B), (True, True))

		keep_away(self.church_b)

		self.assertEqual(self.actions_of(STAFF_B), (False, False))
		self.assertEqual(self.actions_of(STAFF), (True, True), "Branch A keeps its buttons")
		self.assertEqual(as_user(STAFF_B, opt_outs.is_user_kept_away), True)


class TestSuggestions(TriageFlowCase):
	"""Suggestions on new requests leave out such people and churches (churchit.ai.triage). Needs Flow."""

	def test_a_request_of_a_person_who_keeps_out_or_of_a_church_that_keeps_away_queues_nothing(self):
		left_out = make_person("Left Out", LAST_NAME, church=self.church_a, exclude_from_ai=1).name
		of_b = make_person("Branch B", LAST_NAME, church=self.church_b).name
		keep_away(self.church_b)
		queued = self.prayer_request(requestor=self.person)

		self.prayer_request(requestor=left_out)
		self.care_request(person=of_b)
		keep_away(self.church_a)
		self.prayer_request(requestor=self.person)

		self.assertEqual([job["name"] for job in self.queued()], [queued.name])

	def test_the_job_checks_again_before_it_sends_anything(self):
		request = self.prayer_request(requestor=self.person)
		self.run_job(request)[0].assert_called_once()

		frappe.db.set_value("Person", self.person, opt_outs.PERSON_FIELD, 1)

		self.run_job(request)[0].assert_not_called()
