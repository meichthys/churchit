# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.database import get_db
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now

from churchit.church_finances.doctype.fund.fund import (
	add_transaction,
	format_amount,
	remove_transactions,
	warn_of_negative_balance,
)
from churchit.tests.helpers import RollbackEachTest, make_two_churches


class TestFund(FrappeTestCase):
	def _make_fund(self, **values):
		fund = frappe.get_doc(
			{"doctype": "Fund", "fund": f"Test Goal Fund {frappe.generate_hash(length=6)}", **values}
		)
		fund.append(
			"transactions",
			{"amount": 250, "source_type": "Donation", "source": "TEST-DONATION"},
		)
		# Skip Dynamic Link existence check: the math under test only needs the amount.
		fund.flags.ignore_links = True
		return fund.insert(ignore_permissions=True)

	def test_goal_progress_computed_from_balance(self):
		fund = self._make_fund(goal_amount=1000)
		# balance 250 / goal 1000 -> 25%
		self.assertEqual(fund.balance, 250)
		self.assertEqual(fund.goal_progress, 25)

	def test_goal_progress_zero_without_goal(self):
		fund = self._make_fund()
		self.assertEqual(fund.goal_progress, 0)

	def test_goal_progress_can_exceed_100_when_overfunded(self):
		fund = self._make_fund(goal_amount=100)
		# balance 250 / goal 100 -> 250%
		self.assertEqual(fund.goal_progress, 250)


class TestFundMessages(RollbackEachTest):
	def setUp(self):
		super().setUp()
		frappe.local.message_log = []
		self.fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Message Fund"}).insert(
			ignore_permissions=True
		)

	def test_an_amount_shows_in_the_site_currency(self):
		get_default = frappe.db.get_default

		def site_default(key, *args, **kwargs):
			return "GBP" if key == "currency" else get_default(key, *args, **kwargs)

		with patch.object(frappe.db, "get_default", side_effect=site_default):
			amount = format_amount(-1402.5)

		self.assertIn("£", amount)
		self.assertIn("1,402.50", amount)
		self.assertNotIn("$", amount)

	def test_a_change_that_takes_a_fund_below_zero_warns_in_orange(self):
		warn_of_negative_balance(self.fund.name, "{0} would be {1}.", -40)

		[warning] = frappe.get_message_log()
		self.assertEqual(warning["indicator"], "orange")
		self.assertEqual(warning["title"], "Negative Fund Balance")
		self.assertIn("_Test Message Fund", warning["message"])
		self.assertIn(format_amount(-40), warning["message"])

	def test_a_balance_that_stays_at_zero_or_above_says_nothing(self):
		warn_of_negative_balance(self.fund.name, "{0} would be {1}.")
		self.assertEqual(frappe.get_message_log(), [])


def ledger_sum(fund):
	return sum(
		frappe.get_all("Financial Transaction", {"parent": fund, "parenttype": "Fund"}, pluck="amount")
	)


def versions(fund):
	return frappe.db.count("Version", {"ref_doctype": "Fund", "docname": fund})


class TestFundLedger(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Ledger Fund", "goal_amount": 200}
		).insert(ignore_permissions=True)

	def test_add_transaction_writes_one_row_and_settles_the_balance(self):
		before = versions(self.fund.name)
		add_transaction(self.fund.name, 50, "Collection", "_TEST-COL-1", now())
		add_transaction(self.fund.name, 30.555, "Collection", "_TEST-COL-2", now(), notes="Late")

		fund = frappe.get_doc("Fund", self.fund.name)
		self.assertEqual([(row.idx, row.amount) for row in fund.transactions], [(1, 50), (2, 30.56)])
		self.assertEqual(fund.transactions[1].notes, "Late")
		self.assertEqual(fund.balance, ledger_sum(fund.name))
		self.assertEqual(fund.goal_progress, 40.28)
		self.assertEqual(versions(fund.name), before)

	def test_remove_transactions_removes_only_that_sources_rows(self):
		other = frappe.get_doc({"doctype": "Fund", "fund": "_Test Ledger Other Fund"}).insert(
			ignore_permissions=True
		)
		add_transaction(self.fund.name, 50, "Fund Transfer", "_TEST-FT-1", now())
		add_transaction(other.name, -50, "Fund Transfer", "_TEST-FT-1", now())
		add_transaction(self.fund.name, 20, "Fund Transfer", "_TEST-FT-2", now())
		add_transaction(other.name, 5, "Collection", "_TEST-FT-1", now())

		remove_transactions("Fund Transfer", "_TEST-FT-1")

		for fund, balance in ((self.fund.name, 20), (other.name, 5)):
			self.assertEqual(frappe.db.get_value("Fund", fund, "balance"), balance)
			self.assertEqual(ledger_sum(fund), balance)
		self.assertEqual(frappe.db.get_value("Fund", self.fund.name, "goal_progress"), 10)

	def test_a_desk_save_still_settles_the_balance(self):
		add_transaction(self.fund.name, 50, "Collection", "_TEST-COL-1", now())
		fund = frappe.get_doc("Fund", self.fund.name)
		fund.goal_amount = 100
		fund.flags.ignore_links = True
		fund.save(ignore_permissions=True)
		self.assertEqual((fund.balance, fund.goal_progress), (50, 50))


class TestLedgerWriteAfterAWait(FrappeTestCase):
	"""Ledger writers on two connections of their own, so one can wait on the other's locks."""

	funds = ("_Test Waiting Ledger Fund B", "_Test Waiting Ledger Fund C")

	def connect(self):
		conf = frappe.conf
		db = get_db(
			socket=conf.db_socket,
			host=conf.db_host,
			port=conf.db_port,
			user=conf.db_user or conf.db_name,
			password=conf.db_password,
			cur_db_name=conf.db_name,
		)
		db.connect()
		db.sql("set session innodb_lock_wait_timeout = 3")
		self.addCleanup(db.close)
		return db

	def setUp(self):
		self.other, self.late = self.connect(), self.connect()
		self.addCleanup(self.remove_funds)
		for fund in self.funds:
			self.other.sql(
				"insert into `tabFund` (name, fund, goal_amount, creation, modified) values (%s, %s, 100, now(), now())",
				(fund, fund),
			)
		self.other.commit()

	def remove_funds(self):
		self.late.rollback()
		self.other.rollback()
		for table in ("Financial Transaction", "Fund"):
			column = "parent" if table == "Financial Transaction" else "name"
			self.other.sql(f"delete from `tab{table}` where {column} in %s", [self.funds])
		self.other.commit()

	def add_transaction(self, db, fund, amount, source):
		with patch.object(frappe.local, "db", db):
			add_transaction(fund, amount, "Collection", source, now())

	def test_a_late_writer_counts_rows_committed_while_it_waited(self):
		fund = self.funds[0]
		self.late.sql("select count(*) from `tabFinancial Transaction` where parent=%s", fund)
		self.add_transaction(self.other, fund, 5, "_TEST-EARLY")
		self.other.sql("update `tabFund` set goal_amount=30 where name=%s", fund)
		self.other.commit()

		self.add_transaction(self.late, fund, 10, "_TEST-LATE")
		self.late.commit()

		amounts = self.other.sql(
			"select amount from `tabFinancial Transaction` where parent=%s order by amount", fund
		)
		balance = self.other.sql("select balance, goal_progress from `tabFund` where name=%s", fund)
		self.assertEqual([row[0] for row in amounts], [5, 10])
		self.assertEqual(tuple(balance[0]), (15, 50))

	def test_writers_on_two_empty_funds_do_not_wait_on_each_other(self):
		self.add_transaction(self.other, self.funds[0], 5, "_TEST-GIFT-B")
		self.add_transaction(self.late, self.funds[1], 7, "_TEST-GIFT-C")
		self.late.commit()

		with patch.object(frappe.local, "db", self.late):
			self.assertEqual(remove_transactions("Collection", "_TEST-GIFT-C"), [self.funds[1]])
		self.late.commit()
		self.other.commit()

		balances = self.other.sql(
			"select name, balance from `tabFund` where name in %s order by name", [self.funds]
		)
		self.assertEqual([tuple(row) for row in balances], [(self.funds[0], 5), (self.funds[1], 0)])


class TestFundRules(RollbackEachTest):
	def fund(self, **values):
		return frappe.get_doc({"doctype": "Fund", "fund": "_Test Rules Fund", **values})

	def test_a_second_fund_with_the_name_is_refused(self):
		self.fund().insert(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError) as caught:
			self.fund().insert(ignore_permissions=True)

		self.assertIn("There is already a fund called", str(caught.exception))

	def test_a_goal_that_ends_before_it_starts_is_refused(self):
		fund = self.fund(start_date="2026-06-01", end_date="2026-05-01")
		self.assertRaises(frappe.ValidationError, fund.insert, ignore_permissions=True)

	def test_a_stored_reversed_goal_can_still_be_saved(self):
		fund = self.fund().insert(ignore_permissions=True)
		frappe.db.set_value("Fund", fund.name, {"start_date": "2026-06-01", "end_date": "2026-05-01"})

		fund = frappe.get_doc("Fund", fund.name)
		fund.goal_amount = 500
		fund.save(ignore_permissions=True)


class TestFundNamesAcrossChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def fund(self, church, **values):
		return frappe.get_doc({"doctype": "Fund", "fund": "_Test Scoped Fund", "church": church, **values})

	def test_two_churches_may_each_have_a_fund_with_one_name(self):
		self.fund(self.branch_a).insert(ignore_permissions=True)
		self.fund(self.branch_b).insert(ignore_permissions=True)

	def test_a_shared_fund_takes_its_name_for_every_church(self):
		self.fund(self.branch_a, is_shared=1).insert(ignore_permissions=True)

		self.assertRaises(frappe.ValidationError, self.fund(self.branch_b).insert, ignore_permissions=True)

	def test_sharing_a_fund_whose_name_another_church_uses_is_refused(self):
		self.fund(self.branch_a).insert(ignore_permissions=True)
		theirs = self.fund(self.branch_b).insert(ignore_permissions=True)

		theirs.is_shared = 1

		self.assertRaises(frappe.ValidationError, theirs.save, ignore_permissions=True)
