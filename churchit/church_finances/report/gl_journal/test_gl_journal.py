# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from collections import defaultdict

import frappe

from churchit.church_finances.doctype.gl_account_mapping.test_gl_account_mapping import map_account
from churchit.church_finances.report.gl_journal.gl_journal import execute
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

DATES = {"from_date": "2032-05-01", "to_date": "2032-05-31"}


def make_fund(name, church):
	return (
		frappe.get_doc({"doctype": "Fund", "fund": name, "church": church})
		.insert(ignore_permissions=True)
		.name
	)


def collect(gifts, church, date="2032-05-10 10:00:00", submit=True):
	"""A Collection with one Donation for each (payment type, fund, amount, person) of *gifts*."""
	collection = frappe.get_doc(
		{
			"doctype": "Collection",
			"date": date,
			"church": church,
			"expected_total": sum(gift[2] for gift in gifts),
			"donations": [
				{"payment_type": payment_type, "fund": fund, "amount": amount, "person": person}
				for payment_type, fund, amount, person in gifts
			],
		}
	).insert(ignore_permissions=True)
	if submit:
		collection.submit()
	return collection.name


def spend(expense_type, amount, church, date="2032-05-12 10:00:00", title="_Test GL Expense"):
	expense = frappe.get_doc(
		{
			"doctype": "Expense",
			"title": title,
			"type": expense_type,
			"amount": amount,
			"date": date,
			"church": church,
		}
	).insert(ignore_permissions=True)
	expense.submit()
	return expense


def transfer(from_fund, to_fund, amount, church):
	return (
		frappe.get_doc(
			{
				"doctype": "Fund Transfer",
				"from_fund": from_fund,
				"to_fund": to_fund,
				"amount": amount,
				"date": "2032-05-14 10:00:00",
				"church": church,
			}
		)
		.insert(ignore_permissions=True)
		.submit()
	)


def lines_by_source(data):
	"""{source: {(account, debit, credit), ...}} from the report rows."""
	lines = defaultdict(set)
	for row in data:
		lines[row["memo"].rsplit(" ", 1)[1]].add((row["account"], row["debit"], row["credit"]))
	return lines


class TestGLJournal(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.cash = ensure("Payment Type", {"type": "_Test GL Cash"})
		cls.card = ensure("Payment Type", {"type": "_Test GL Card"})
		cls.general = make_fund("_Test GL General", cls.branch_a)
		cls.missions = make_fund("_Test GL Missions", cls.branch_a)
		cls.fund_b = make_fund("_Test GL Fund B", cls.branch_b)
		cls.supplies = ensure(
			"Expense Type", {"type": "_Test GL Supplies"}, {"type": "_Test GL Supplies", "fund": cls.general}
		)
		cls.supplies_b = ensure(
			"Expense Type",
			{"type": "_Test GL Supplies B"},
			{"type": "_Test GL Supplies B", "fund": cls.fund_b},
		)
		cls.giver = make_person("_Test GL", "Giver", church=cls.branch_a).name
		cls.giver_b = make_person("_Test GL", "Giver B", church=cls.branch_b).name

		for mapping_for, record, account in (
			("Payment Type", cls.cash, "1010 Cash"),
			("Payment Type", cls.card, "1020 Card Clearing"),
			("Fund", cls.general, "3010 General"),
			("Fund", cls.missions, "3020 Missions"),
			("Expense Type", cls.supplies, "5010 Supplies"),
			("Church", cls.branch_a, "1000 Checking A"),
		):
			map_account(mapping_for, record, account, cls.branch_a)
		map_account("Payment Type", cls.cash, "1010 Cash B", cls.branch_b)
		map_account("Fund", cls.fund_b, "3010 General B", cls.branch_b)
		map_account("Expense Type", cls.supplies_b, "5010 Supplies B", cls.branch_b)
		map_account("Church", cls.branch_b, "1000 Checking B", cls.branch_b)

		cls.finance_a = ensure_user("_test_gl_journal_a@example.com", "GL A", roles=("Church Finance",))
		cls.finance_b = ensure_user("_test_gl_journal_b@example.com", "GL B", roles=("Church Finance",))
		set_user_church(cls.finance_a, cls.branch_a)
		set_user_church(cls.finance_b, cls.branch_b)

	def journal(self, user, filters=None):
		frappe.set_user(user)
		try:
			return execute({**DATES, **(filters or {})})[1]
		finally:
			frappe.set_user("Administrator")

	def test_each_document_balances(self):
		collection = collect(
			[
				(self.cash, self.general, 100, self.giver),
				(self.card, self.general, 50, self.giver),
				(self.card, self.missions, 25, None),
			],
			self.branch_a,
		)
		expense = spend(self.supplies, 30, self.branch_a).name
		fund_transfer = transfer(self.general, self.missions, 20, self.branch_a).name

		data = self.journal(self.finance_a)

		lines = lines_by_source(data)
		self.assertEqual(
			lines[collection],
			{
				("1010 Cash", 100, 0),
				("1020 Card Clearing", 75, 0),
				("3010 General", 0, 150),
				("3020 Missions", 0, 25),
			},
		)
		self.assertEqual(lines[expense], {("5010 Supplies", 30, 0), ("1000 Checking A", 0, 30)})
		self.assertEqual(lines[fund_transfer], {("3010 General", 20, 0), ("3020 Missions", 0, 20)})
		for source, source_lines in lines.items():
			debits = sum(debit for _account, debit, _credit in source_lines)
			credits = sum(credit for _account, _debit, credit in source_lines)
			self.assertEqual(debits, credits, source)
		self.assertIn(f"Collection {collection}", {row["memo"] for row in data})

	def test_a_document_that_does_not_balance_is_refused(self):
		collection = collect([(self.cash, self.general, 100, None)], self.branch_a)
		frappe.db.set_value("Collection Fund Total", {"parent": collection}, "total", 90)

		with self.assertRaises(frappe.ValidationError) as raised:
			self.journal(self.finance_a)

		self.assertIn(collection, str(raised.exception))

	def test_a_missing_mapping_lists_every_record(self):
		unmapped_fund = make_fund("_Test GL Unmapped Fund", self.branch_a)
		unmapped_type = ensure("Payment Type", {"type": "_Test GL Unmapped Type"})
		unmapped_expense = ensure(
			"Expense Type",
			{"type": "_Test GL Unmapped Expense"},
			{"type": "_Test GL Unmapped Expense", "fund": self.general},
		)
		collect(
			[(unmapped_type, unmapped_fund, 10, None), (self.cash, unmapped_fund, 5, None)], self.branch_a
		)
		collect([(self.cash, unmapped_fund, 3, None)], self.branch_a)
		spend(unmapped_expense, 7, self.branch_a)
		frappe.delete_doc(
			"GL Account Mapping",
			frappe.db.get_value("GL Account Mapping", {"mapping_for": "Church", "record": self.branch_a}),
			ignore_permissions=True,
		)

		with self.assertRaises(frappe.ValidationError) as raised:
			self.journal(self.finance_a)

		message = str(raised.exception)
		for title in ("_Test GL Unmapped Fund", unmapped_type, unmapped_expense, "_Test Scope A"):
			self.assertIn(title, message)
		self.assertEqual(message.count("_Test GL Unmapped Fund"), 1)

	def test_a_record_mapped_twice_is_refused(self):
		duplicate = frappe.new_doc("GL Account Mapping")
		duplicate.update(
			{
				"mapping_for": "Payment Type",
				"record": self.cash,
				"account": "1015 Petty Cash",
				"church": self.branch_a,
			}
		)
		duplicate.set_new_name()
		duplicate.db_insert()  # As two saves that raced past the check would leave it.

		with self.assertRaises(frappe.ValidationError) as raised:
			self.journal(self.finance_a)

		self.assertIn("1015 Petty Cash", str(raised.exception))

	def test_church_b_sees_no_church_a_row_and_no_person(self):
		collect([(self.cash, self.fund_b, 40, self.giver_b)], self.branch_b)
		mine = collect([(self.cash, self.fund_b, 60, self.giver_b)], self.branch_b)
		alms = spend(self.supplies_b, 15, self.branch_b, title="Alms: _Test GL Giver B").name
		theirs = collect([(self.cash, self.general, 80, self.giver)], self.branch_a)
		# Church A's unmapped record would throw if its Collection leaked into the journal.
		collect([(self.card, make_fund("_Test GL Unmapped A", self.branch_a), 9, None)], self.branch_a)

		data = self.journal(self.finance_b)

		sources = set(lines_by_source(data))
		self.assertTrue({mine, alms} <= sources)
		self.assertNotIn(theirs, sources)
		values = " ".join(str(value) for row in data for value in row.values())
		for person in (self.giver_b, "Giver B"):
			self.assertNotIn(person, values)

	def test_only_submitted_records_in_the_dates_count(self):
		last_day = collect([(self.cash, self.general, 10, None)], self.branch_a, date="2032-05-31 23:30:00")
		next_day = collect([(self.cash, self.general, 11, None)], self.branch_a, date="2032-06-01 00:00:00")
		draft = collect([(self.cash, self.general, 12, None)], self.branch_a, submit=False)
		cancelled = spend(self.supplies, 13, self.branch_a)
		cancelled.cancel()

		sources = set(lines_by_source(self.journal(self.finance_a)))

		self.assertIn(last_day, sources)
		self.assertFalse({next_day, draft, cancelled.name} & sources)

	def test_the_journal_waits_for_both_dates(self):
		collect([(self.cash, self.general, 10, None)], self.branch_a)

		self.assertEqual(self.journal(self.finance_a, {"to_date": None}), [])


class TestGLJournalSingleChurch(RollbackEachTest):
	def setUp(self):
		super().setUp()
		force_single_church()

	def test_a_single_church_site_journals_without_a_church(self):
		cash = ensure("Payment Type", {"type": "_Test GL Cash"})
		fund = make_fund("_Test GL Single Fund", None)
		supplies = ensure(
			"Expense Type",
			{"type": "_Test GL Single Supplies"},
			{"type": "_Test GL Single Supplies", "fund": fund},
		)
		for mapping_for, record, account in (
			("Payment Type", cash, "1010 Cash"),
			("Fund", fund, "3010 General"),
			("Expense Type", supplies, "5010 Supplies"),
			("Church", ensure_root_church(), "1000 Checking"),
		):
			map_account(mapping_for, record, account)
		collection = collect([(cash, fund, 100, None)], None)
		expense = spend(supplies, 30, None).name

		lines = lines_by_source(execute(DATES)[1])

		self.assertEqual(lines[collection], {("1010 Cash", 100, 0), ("3010 General", 0, 100)})
		self.assertEqual(lines[expense], {("5010 Supplies", 30, 0), ("1000 Checking", 0, 30)})
