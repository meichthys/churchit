# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Explain this report: which reports AI explains, the rows it gets (the caller's own, never the
browser's), the agent that gets them and the answer it may show.

runner.start is patched, so no test needs Flow or calls a model; the runner has its own tests.
"""

import json
from unittest.mock import patch

import frappe

from churchit.ai import reports, runner
from churchit.ai.private_doctypes import RECOMMENDED
from churchit.ai.switch import SETTINGS, extend_bootinfo
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches, pop_logs

STAFF_A = "_test_explain_staff_a@example.com"
FINANCE_A = "_test_explain_finance_a@example.com"
CARE_A = "_test_explain_care_a@example.com"
WEBSITE_USER = "_test_explain_website@example.com"
START = "churchit.ai.reports.runner.start"


def church_user(email: str, roles: tuple, church: str) -> str:
	ensure_user(email, "Explain", roles)
	set_user_church(email, church)
	return email


class ExplainTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		church_user(STAFF_A, ("Church Staff",), cls.church_a)
		church_user(FINANCE_A, ("Church Staff", "Church Finance"), cls.church_a)
		church_user(CARE_A, ("Church Staff", "Church Pastoral Care"), cls.church_a)
		ensure_user(WEBSITE_USER, "Explain Website", roles=())
		cls.person_a = make_person("_Test Explain", "Alpha", church=cls.church_a).full_name
		cls.person_b = make_person("_Test Explain", "Beta", church=cls.church_b).full_name

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, "enabled", 1)

	def explain(self, user: str, report_name: str, filters=None) -> tuple[dict, dict]:
		"""explain_report as *user*; the answer and what runner.start got."""
		frappe.set_user(user)
		with patch(START, return_value={"token": "t" * 32}) as start:
			answer = reports.explain_report(report_name, json.dumps(filters or {}))
		feature, prompt = start.call_args.args
		return answer, {"feature": feature, "prompt": prompt, **start.call_args.kwargs}


class TestWhichReports(ExplainTestCase):
	def test_the_children_report_and_each_no_explain_report_are_refused(self):
		for report_name in reports.NO_EXPLAIN:
			with self.subTest(report_name):
				self.assertTrue(frappe.db.exists("Report", report_name))
				self.assertRaisesRegex(
					frappe.ValidationError,
					"children or can hold private prayer",
					self.explain,
					STAFF_A,
					report_name,
				)

	def test_the_boot_hides_the_explain_item_of_each_no_explain_report(self):
		bootinfo = frappe._dict()
		extend_bootinfo(bootinfo)
		self.assertEqual(bootinfo.churchit["ai"]["no_explain"], list(reports.NO_EXPLAIN))

	def test_only_churchit_script_reports_are_explained(self):
		"""A churchit Report Builder report, and a Frappe script report that only a System Manager opens."""
		for user, report_name in (
			(STAFF_A, "First-Time Visitors"),
			("Administrator", "Permitted Documents For User"),
		):
			with self.subTest(report_name):
				self.assertRaisesRegex(
					frappe.ValidationError,
					"only churchit's script reports",
					self.explain,
					user,
					report_name,
				)

	def test_a_user_without_church_finance_cannot_explain_a_finance_report(self):
		self.assertRaises(frappe.PermissionError, self.explain, STAFF_A, "Donations")

		_answer, started = self.explain(FINANCE_A, "Donations")
		self.assertIn("Collection", started["sends"], "Giving records go to Private Work")

	def test_a_fund_report_counts_as_giving_records(self):
		"""Its doctype is Fund, but its rows total gifts."""
		_answer, started = self.explain(FINANCE_A, "Fund Balances")
		self.assertEqual(frappe.db.get_value("Report", "Fund Balances", "ref_doctype"), "Fund")
		self.assertIn("Collection", started["sends"])

	def test_ai_off_and_a_website_user_are_refused(self):
		frappe.db.set_single_value(SETTINGS, "enabled", 0)
		self.assertRaisesRegex(frappe.PermissionError, "AI is turned off", self.explain, STAFF_A, "People")

		frappe.db.set_single_value(SETTINGS, "enabled", 1)
		self.assertRaises(frappe.PermissionError, self.explain, WEBSITE_USER, "People")


class TestWhatTheAIGets(ExplainTestCase):
	def test_the_report_runs_again_as_the_caller_and_never_takes_rows_from_the_browser(self):
		answer, started = self.explain(STAFF_A, "People", {"person_name": "_Test Explain"})

		names = [row[0] for row in answer["rows"]]
		self.assertEqual(names, [self.person_a], "Only the caller's church")
		self.assertIn(self.person_a, started["prompt"])
		self.assertNotIn(self.person_b, started["prompt"])
		self.assertEqual(answer["token"], "t" * 32)
		self.assertEqual(started["check"], reports.CHECK)
		self.assertEqual(started["sends"], {"Person", "Membership Type", "Member Status"})

	def test_the_rows_are_data_after_the_instructions(self):
		_answer, started = self.explain(STAFF_A, "People", {"person_name": "_Test Explain"})
		instructions, data = started["prompt"].split('<data source="report rows">')

		self.assertIn('"summary"', instructions)
		self.assertNotIn(self.person_a, instructions)
		self.assertIn(self.person_a, data)
		self.assertTrue(data.endswith("</data>"))

	def test_an_access_log_row_names_the_report(self):
		filters = {"user": STAFF_A, "method": reports.ACCESS_LOG_METHOD, "report_name": "People"}
		pop_logs("Access Log", filters)
		self.explain(STAFF_A, "People", {"person_name": "_Test Explain"})
		frappe.set_user("Administrator")
		self.assertEqual(len(pop_logs("Access Log", filters)), 1)

	def test_a_report_on_a_private_doctype_sends_records_of_that_doctype(self):
		"""The runner gives them to Private Work, because Visitation Log is recommended for the list."""
		_answer, started = self.explain(CARE_A, "Visitation Followups Needed")
		self.assertIn("Visitation Log", started["sends"])
		self.assertIn("Visitation Log", RECOMMENDED)

	def test_at_most_200_rows_without_masked_and_health_fields(self):
		columns = [
			{"fieldname": "full_name", "label": "Name"},
			{"fieldname": "medical_notes", "label": "Medical Notes"},
			{"fieldname": "attendance", "label": "Attendance", "fieldtype": "Int"},
		]
		rows = [
			{"full_name": f"P{index}", "medical_notes": "Asthma", "attendance": index} for index in range(250)
		]
		rows.append(["Total", "", 31125])

		table = reports.get_table("Person", columns, rows)

		self.assertEqual(table["columns"], ["Name", "Attendance"])
		self.assertEqual((len(table["rows"]), table["total_rows"]), (200, 251))
		self.assertEqual(table["rows"][3], ["P3", 3])
		self.assertNotIn("Asthma", json.dumps(table))
		self.assertIn("the first 200 of 251 rows", reports.get_prompt("People", {}, table))

	def test_a_field_the_caller_may_not_read_is_dropped(self):
		"""Person.last_visited_on is for pastoral care (permlevel 3)."""
		columns = [
			{"fieldname": "full_name", "label": "Name"},
			{"fieldname": "last_visited_on", "label": "Visited"},
		]
		rows = [{"full_name": "P1", "last_visited_on": "2026-11-01"}]

		frappe.set_user(STAFF_A)
		self.assertEqual(reports.get_table("Person", columns, rows)["columns"], ["Name"])
		frappe.set_user(CARE_A)
		self.assertEqual(reports.get_table("Person", columns, rows)["columns"], ["Name", "Visited"])


class TestAnswer(ExplainTestCase):
	def test_the_answer_keeps_its_text_and_three_questions(self):
		answer = {
			"summary": "Attendance <img src=https://example.com/x.png> rose.",
			"trend": 3,
			"questions": ["Who?", "", "Why?", "When?", "Where?", 7],
			"extra": "dropped",
		}
		self.assertEqual(
			reports.check_explanation(answer),
			{
				"summary": "Attendance <img src=https://example.com/x.png> rose.",
				"trend": "",
				"questions": ["Who?", "Why?", "When?"],
			},
		)

	def test_an_answer_without_a_summary_cannot_be_used(self):
		for answer in ([], {"trend": "Up"}, {"summary": 5}):
			with self.subTest(answer):
				self.assertRaisesRegex(
					frappe.ValidationError, runner.UNUSABLE, reports.check_explanation, answer
				)
