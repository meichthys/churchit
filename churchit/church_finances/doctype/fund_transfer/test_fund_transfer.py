# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.utils import add_years, now, today

from churchit.church_finances.doctype.fund.fund import format_amount
from churchit.church_foundations.church_access import set_user_church
from churchit.patches.v1_0 import name_funds_in_transfer_notes, retitle_fund_transfers
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches


class TestFundTransfer(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.from_fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Transfer From"})
			.insert(ignore_permissions=True)
			.name
		)
		self.to_fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Transfer To"})
			.insert(ignore_permissions=True)
			.name
		)

	def _make_transfer(self, amount=50, **values):
		data = {
			"doctype": "Fund Transfer",
			"from_fund": self.from_fund,
			"to_fund": self.to_fund,
			"amount": amount,
			"date": now(),
		}
		data.update(values)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	def test_the_title_names_the_funds(self):
		self.assertEqual(self._make_transfer().title, "_Test Transfer From to _Test Transfer To")

	def test_the_patch_retitles_an_old_transfer_and_can_run_again(self):
		transfer = self._make_transfer()
		frappe.db.set_value(
			"Fund Transfer", transfer.name, "title", f"{self.from_fund} to {self.to_fund} - 2026-10-17"
		)

		retitle_fund_transfers.execute()
		retitle_fund_transfers.execute()

		self.assertEqual(
			frappe.db.get_value("Fund Transfer", transfer.name, "title"),
			"_Test Transfer From to _Test Transfer To",
		)

	def test_same_source_and_destination_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_transfer(to_fund=self.from_fund)

	def test_non_positive_amount_rejected(self):
		with self.assertRaises(ValidationError):
			self._make_transfer(amount=0)

	def test_a_transfer_with_no_source_names_the_missing_field(self):
		with self.assertRaises(frappe.MandatoryError):
			self._make_transfer(from_fund=None)

	def test_submit_moves_balance_between_funds(self):
		self._make_transfer(amount=50).submit()
		self.assertEqual(frappe.db.get_value("Fund", self.from_fund, "balance"), -50)
		self.assertEqual(frappe.db.get_value("Fund", self.to_fund, "balance"), 50)

	def test_submit_writes_one_ledger_row_on_each_fund_without_saving_them(self):
		versions = frappe.db.count("Version", {"ref_doctype": "Fund"})
		transfer = self._make_transfer(amount=50, notes="Roof")
		transfer.submit()

		ledger = {"source_type": "Fund Transfer", "source": transfer.name}
		self.assertEqual(
			frappe.get_all("Financial Transaction", ledger, ["parent", "amount", "notes"], order_by="amount"),
			[
				{"parent": self.from_fund, "amount": -50, "notes": "Transfer to _Test Transfer To: Roof"},
				{"parent": self.to_fund, "amount": 50, "notes": "Transfer from _Test Transfer From: Roof"},
			],
		)
		self.assertEqual(frappe.db.count("Version", {"ref_doctype": "Fund"}), versions)

		transfer.cancel()
		self.assertFalse(frappe.db.exists("Financial Transaction", ledger))

	def test_the_patch_names_the_funds_in_old_notes_and_can_run_again(self):
		transfer = self._make_transfer(amount=50, notes="Roof")
		transfer.submit()
		ledger = {"source_type": "Fund Transfer", "source": transfer.name}
		old_notes = {
			self.from_fund: f"Transfer to {self.to_fund}: Roof",
			self.to_fund: f"Transfer from {self.from_fund}",
		}
		for fund, notes in old_notes.items():
			frappe.db.set_value("Financial Transaction", {**ledger, "parent": fund}, "notes", notes)

		name_funds_in_transfer_notes.execute()
		name_funds_in_transfer_notes.execute()

		self.assertEqual(
			frappe.get_all("Financial Transaction", ledger, ["parent", "notes"], order_by="amount"),
			[
				{"parent": self.from_fund, "notes": "Transfer to _Test Transfer To: Roof"},
				{"parent": self.to_fund, "notes": "Transfer from _Test Transfer From"},
			],
		)

	def test_a_draft_that_takes_the_source_below_zero_warns_in_orange(self):
		frappe.local.message_log = []
		self._make_transfer(amount=50)

		[warning] = frappe.get_message_log()
		self.assertEqual(warning["indicator"], "orange")
		self.assertIn("_Test Transfer From", warning["message"])
		self.assertIn(format_amount(-50), warning["message"])

	def test_submit_alerts_the_move_in_the_site_currency(self):
		transfer = self._make_transfer(amount=1500)
		frappe.local.message_log = []
		transfer.submit()

		alert, warning = frappe.get_message_log()
		self.assertTrue(alert["alert"])
		self.assertIn(format_amount(1500), alert["message"])
		self.assertNotIn("$", alert["message"].replace(format_amount(1500), ""))
		self.assertIn(format_amount(-1500), warning["message"])

	def test_a_typed_date_far_from_today_warns_but_saves(self):
		transfer = self._make_transfer(amount=50)
		transfer.flags.ignore_permissions = False
		transfer.date = "2206-01-01 10:00:00"
		frappe.local.message_log = []
		transfer.save()

		messages = [message["message"] for message in frappe.get_message_log()]
		self.assertTrue(any("more than 30 days after today" in message for message in messages), messages)

		transfer.date = f"{add_years(today(), -2)} 10:00:00"
		frappe.local.message_log = []
		transfer.save()
		messages = [message["message"] for message in frappe.get_message_log()]
		self.assertTrue(any("more than a year before today" in message for message in messages), messages)

	def test_cancel_reverses_the_transfer(self):
		transfer = self._make_transfer(amount=50)
		transfer.submit()
		transfer.cancel()
		self.assertEqual(frappe.db.get_value("Fund", self.from_fund, "balance"), 0)
		self.assertEqual(frappe.db.get_value("Fund", self.to_fund, "balance"), 0)


class TestFundTransferAcrossChurches(RollbackEachTest):
	"""Only the church that owns the source fund moves its money."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.finance_b = ensure_user(
			"_test_transfer_finance_b@example.com", "Finance B", roles=("Church Finance",)
		)
		set_user_church(cls.finance_b, cls.branch_b)
		cls.fund_a, cls.other_fund_a, cls.fund_b, cls.shared_fund = (
			frappe.get_doc({"doctype": "Fund", "fund": name, "church": church, "is_shared": shared})
			.insert(ignore_permissions=True)
			.name
			for name, church, shared in (
				("_Test Transfer A", cls.branch_a, 0),
				("_Test Transfer Other A", cls.branch_a, 0),
				("_Test Transfer B", cls.branch_b, 0),
				("_Test Transfer Shared", cls.branch_a, 1),
			)
		)

	def transfer(self, from_fund, to_fund, **values):
		return frappe.get_doc(
			{
				"doctype": "Fund Transfer",
				"from_fund": from_fund,
				"to_fund": to_fund,
				"amount": 25,
				"date": now(),
				**values,
			}
		)

	def test_another_church_cannot_move_a_churchs_money(self):
		"""Frappe checks create and submit on the church the caller sends, before it fetches the fund's."""
		frappe.set_user(self.finance_b)
		for to_fund in (self.other_fund_a, self.shared_fund):
			with self.assertRaises(frappe.PermissionError, msg=to_fund):
				self.transfer(self.fund_a, to_fund, church=self.branch_b, docstatus=1).insert()

		self.assertEqual(self.transfer(self.fund_b, self.shared_fund).insert().church, self.branch_b)

	def test_another_church_cannot_take_a_transfer_over(self):
		"""Naming its own fund moves the transfer to the caller's church, so the stored church counts too."""
		name = self.transfer(self.fund_a, self.shared_fund).insert(ignore_permissions=True).name
		frappe.set_user(self.finance_b)
		transfer = frappe.get_doc("Fund Transfer", name)
		transfer.update({"from_fund": self.fund_b, "church": self.branch_b})

		with self.assertRaises(frappe.PermissionError):
			transfer.save()
