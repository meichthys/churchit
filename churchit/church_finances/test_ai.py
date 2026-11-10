# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Suggest Type sends an expense's notes, a business vendor's name and its church's Expense Types, to
finance users only, and keeps an answer only when it is one of those types.

Tests never call a model: runner.start is patched, and the check runs as the caller.
"""

import json

import frappe

from churchit.ai import runner
from churchit.ai.test_runner import WRITER, FlowRunnerTestCase, flow_session, staff_user
from churchit.church_finances import ai
from churchit.church_finances.test_finance_scope import make_expense, make_fund
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.church_people.test_ai_actions import data_of, prompt_of, run_action
from churchit.tests.helpers import ensure, ensure_user, make_person, make_two_churches, pop_logs

AMOUNT = 4321.87


def make_type(name: str, fund: str) -> str:
	return ensure("Expense Type", {"type": name}, {"type": name, "fund": fund})


def make_vendor(name: str, church: str, **values) -> str:
	vendor = {"doctype": "Vendor", "vendor_name": name, "church": church, "is_active": 1, **values}
	return frappe.get_doc(vendor).insert(ignore_permissions=True).name


class ExpenseTestCase(AITestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.finance = ensure_user("_test_ai_finance@example.com", "AI Finance", ["Church Finance"])
		set_user_church(cls.finance, cls.branch_a)

	def setUp(self):
		super().setUp()
		self.office = make_type("_Test AI Office Supplies", make_fund("_Test AI Fund A", self.branch_a).name)
		self.travel = make_type("_Test AI Travel", make_fund("_Test AI Fund B", self.branch_b).name)
		shared = make_fund("_Test AI Shared Fund", self.branch_a, is_shared=1).name
		self.shared = make_type("_Test AI Shared Repairs", shared)
		self.business = make_vendor("_Test AI Paper Company", self.branch_a, is_business=1)
		make_person("Quinlan", "Vendorperson", church=self.branch_a)
		self.person_vendor = make_vendor("Quinlan Vendorperson", self.branch_a, is_business=1)
		self.expense = make_expense(
			"Reimburse Quinlan",
			self.office,
			AMOUNT,
			church=self.branch_a,
			vendor=self.business,
			notes="Printer paper for the office",
		).name


class TestSuggestExpenseType(ExpenseTestCase):
	def test_the_prompt_holds_the_notes_the_vendor_and_the_churchs_types_only(self):
		_result, call = run_action(self.finance, ai.suggest_expense_type, self.expense)

		data, prompt = data_of(call), prompt_of(call)
		self.assertIn("Vendor: _Test AI Paper Company", data)
		self.assertIn("Notes: Printer paper for the office", data)
		self.assertIn(self.office, prompt)
		self.assertIn(self.shared, prompt)
		self.assertNotIn(self.travel, prompt)
		for value in ("4321", "Reimburse Quinlan", "_Test AI Fund A"):
			self.assertNotIn(value, prompt)
		self.assertEqual(call.kwargs["sends"], ("Expense",))
		self.assertEqual(call.kwargs["reference_name"], self.expense)

	def test_a_person_vendors_name_is_not_in_the_prompt(self):
		frappe.db.set_value("Expense", self.expense, "vendor", self.person_vendor)
		_result, call = run_action(self.finance, ai.suggest_expense_type, self.expense)

		self.assertNotIn("Vendorperson", prompt_of(call))
		self.assertIn("Printer paper", data_of(call))

	def test_a_vendor_not_ticked_as_a_business_is_not_in_the_prompt(self):
		vendor = make_vendor("_Test AI Sole Trader", self.branch_a)
		frappe.db.set_value("Expense", self.expense, "vendor", vendor)
		_result, call = run_action(self.finance, ai.suggest_expense_type, self.expense)

		self.assertNotIn("Sole Trader", prompt_of(call))
		self.assertIn("Printer paper", data_of(call))

	def test_a_vendor_with_a_persons_email_counts_as_a_person(self):
		person = make_person("Ottilie", "Emailperson", church=self.branch_a)
		person.append("emails", {"email_address": "ottilie.emailperson@example.com"})
		person.save(ignore_permissions=True)
		vendor = make_vendor(
			"Ottilie Crafts", self.branch_a, email="ottilie.emailperson@example.com", is_business=1
		)

		self.assertIsNone(as_user(self.finance, ai.get_vendor_name, vendor))
		self.assertEqual(as_user(self.finance, ai.get_vendor_name, self.business), "_Test AI Paper Company")

	def test_a_new_expense_sends_its_typed_values(self):
		values = {"church": self.branch_a, "vendor": self.business, "notes": "Paint", "amount": AMOUNT}
		_result, call = run_action(self.finance, ai.suggest_expense_type, json.dumps(values))

		self.assertIn("Notes: Paint", data_of(call))
		self.assertNotIn("4321", prompt_of(call))
		self.assertIsNone(call.kwargs["reference_name"])

	def test_the_suggestion_is_one_of_the_churchs_expense_types(self):
		answer = {"church": self.branch_a, "type": self.office}
		self.assertEqual(as_user(self.finance, ai.check_expense_type, answer), answer)
		self.assertEqual(
			as_user(self.finance, ai.check_expense_type, {**answer, "type": self.shared}),
			{**answer, "type": self.shared},
		)
		for wrong in ({**answer, "type": self.travel}, {**answer, "type": "Coffee"}, {**answer, "type": ""}):
			with self.subTest(wrong=wrong):
				with self.assertRaisesRegex(frappe.ValidationError, ai.NO_MATCH):
					as_user(self.finance, ai.check_expense_type, wrong)
		self.assertRaises(
			frappe.ValidationError,
			as_user,
			self.finance,
			ai.check_expense_type,
			{**answer, "church": self.branch_b},
		)

	def test_a_malformed_answer_is_refused_as_unusable(self):
		for answer in ({"church": [self.branch_a], "type": self.office}, ["type"]):
			with self.subTest(answer=answer):
				self.assertRaises(
					frappe.ValidationError, as_user, self.finance, ai.check_expense_type, answer
				)

	def test_each_sent_expense_is_logged(self):
		filters = {"reference_document": self.expense, "method": f"AI: {ai.EXPENSE_TYPE_SUGGESTION}"}
		pop_logs("Access Log", filters)
		run_action(self.finance, ai.suggest_expense_type, self.expense)
		self.assertEqual(len(pop_logs("Access Log", filters)), 1)


class TestExpenseRefusals(ExpenseTestCase):
	def test_non_finance_users_are_refused(self):
		for user in (self.staff, self.member):
			with self.subTest(user=user):
				self.assertRaises(
					frappe.PermissionError, run_action, user, ai.suggest_expense_type, self.expense
				)
		_result, call = run_action(self.manager, ai.suggest_expense_type, self.expense)
		self.assertTrue(call)

	def test_another_churchs_expense_and_a_new_one_of_another_church_are_refused(self):
		fund_b = frappe.db.get_value("Expense Type", self.travel, "fund")
		theirs = make_expense(
			"_Test AI B", self.travel, 10, church=self.branch_b, notes="Bus", associated_fund=fund_b
		)
		new_b = json.dumps({"church": self.branch_b, "notes": "Bus"})
		self.assertRaises(
			frappe.PermissionError, run_action, self.finance, ai.suggest_expense_type, theirs.name
		)
		self.assertRaises(frappe.PermissionError, run_action, self.finance, ai.suggest_expense_type, new_b)

	def test_a_church_that_keeps_away_and_ai_off_are_refused(self):
		frappe.db.set_value("Church", self.branch_a, "keep_away_from_ai", 1)
		self.assertRaises(
			frappe.PermissionError, run_action, self.finance, ai.suggest_expense_type, self.expense
		)
		frappe.db.set_value("Church", self.branch_a, "keep_away_from_ai", 0)
		set_ai(0)
		self.assertRaises(
			frappe.PermissionError, run_action, self.finance, ai.suggest_expense_type, self.expense
		)

	def test_a_submitted_or_missionary_expense_is_refused(self):
		frappe.db.set_value("Expense", self.expense, "docstatus", 1)
		self.assertRaises(
			frappe.ValidationError, run_action, self.finance, ai.suggest_expense_type, self.expense
		)
		missionary = json.dumps({"church": self.branch_a, "notes": "Support", "missionary": "MSNRY-0001"})
		self.assertRaises(
			frappe.ValidationError, run_action, self.finance, ai.suggest_expense_type, missionary
		)


class TestExpenseTypeOnFlow(FlowRunnerTestCase):
	"""An expense is a church record: it needs a No training, Zero retention or Local model. Needs Flow."""

	def test_suggest_type_runs_on_writer_and_needs_a_model_that_keeps_records(self):
		church_a = make_two_churches()[1]
		finance = staff_user("_test_ai_finance_flow@example.com", church_a, ("Church Finance", "Flow User"))
		fund = make_fund("_Test AI Flow Fund", church_a).name
		expense = json.dumps({"church": church_a, "notes": "Paper"})
		make_type("_Test AI Flow Supplies", fund)

		frappe.set_user(finance)
		self.set_labels("May train", "May train")
		self.assertRaises(frappe.PermissionError, ai.suggest_expense_type, expense)
		self.set_labels("No training", "May train")
		with flow_session() as new_session:
			ai.suggest_expense_type(expense)
		self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")
		self.assertEqual(new_session.call_args.args[0].name, WRITER)
