# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Max
from frappe.utils import flt, fmt_money, get_link_to_form, get_url, getdate
from frappe.utils.print_format_generator import get_qr_code

from churchit.church_scope import is_multi_church
from churchit.unique_names import refuse_a_second_with_this_name


class Fund(Document):
	def validate(self):
		refuse_a_second_with_this_name(
			self, "fund", _("There is already a fund called {0}. Give this fund another name.")
		)
		if self.is_goal_period_reversed:
			frappe.throw(_("The End Date cannot be before the Start Date."))

	def before_save(self):
		self.recalculate_balance()
		self.update_goal_progress()

	@property
	def is_goal_period_reversed(self) -> bool:
		"""True when this save sets an end before the start. A period stored that way can still be saved."""
		changed = self.is_new() or self.has_value_changed("start_date") or self.has_value_changed("end_date")
		return bool(
			changed
			and self.start_date
			and self.end_date
			and getdate(self.end_date) < getdate(self.start_date)
		)

	def recalculate_balance(self):
		self.balance = sum(transaction.amount or 0 for transaction in self.transactions)

	def update_goal_progress(self):
		self.goal_progress = get_goal_progress(self.balance, self.goal_amount)


def get_goal_progress(balance: float, goal_amount: float) -> float:
	"""Percentage of the goal amount reached by the balance."""
	if not goal_amount or goal_amount <= 0:
		return 0
	return (balance or 0) / goal_amount * 100


def add_transaction(fund: str, amount: float, source_type: str, source: str, date, notes: str | None = None):
	"""Add one ledger row to a Fund under its row lock, without saving the whole Fund.

	A caller that touches two funds calls this in fund name order, so two writers cannot deadlock.
	The balance comes from the locked Fund row, which is current after a wait. A locking read
	of the ledger rows would take gap locks that block writers on other Funds.
	"""
	balance, goal_amount = frappe.db.get_value("Fund", fund, ["balance", "goal_amount"], for_update=True)
	Transaction = frappe.qb.DocType("Financial Transaction")
	# idx only orders the rows. After a wait it can repeat the other writer's idx.
	last_idx = (
		frappe.qb.from_(Transaction)
		.select(Max(Transaction.idx))
		.where((Transaction.parent == fund) & (Transaction.parenttype == "Fund"))
		.run()[0][0]
	)
	row = frappe.get_doc(
		{
			"doctype": "Financial Transaction",
			"parent": fund,
			"parenttype": "Fund",
			"parentfield": "transactions",
			"idx": (last_idx or 0) + 1,
			"source_type": source_type,
			"source": source,
			"date": date,
			"notes": notes,
		}
	)
	row.amount = flt(amount, row.precision("amount"))
	row.db_insert()
	set_balance(fund, (balance or 0) + row.amount, goal_amount)


def remove_transactions(source_type: str, source: str) -> list[str]:
	"""Delete a source document's ledger rows and return the Funds they were on.

	Rows are deleted by name: no index covers the source, so a delete by source would lock
	the rows of every Fund.
	"""
	rows_by_fund = {}
	# church-scope: the rows of one source document, which its own permission check already allowed
	for row in frappe.get_all(
		"Financial Transaction",
		{"parenttype": "Fund", "source_type": source_type, "source": source},
		["name", "parent", "amount"],
	):
		rows_by_fund.setdefault(row.parent, []).append(row)

	funds = sorted(rows_by_fund)
	for fund in funds:
		balance, goal_amount = frappe.db.get_value("Fund", fund, ["balance", "goal_amount"], for_update=True)
		rows = rows_by_fund[fund]
		frappe.db.delete("Financial Transaction", {"name": ("in", [row.name for row in rows])})
		set_balance(fund, (balance or 0) - sum(row.amount or 0 for row in rows), goal_amount)
	return funds


def set_balance(fund: str, balance: float, goal_amount: float):
	"""Write a Fund's balance and goal progress without a save, as `Fund.before_save` sets them."""
	balance = flt(balance, frappe.get_precision("Fund", "balance"))
	frappe.db.set_value(
		"Fund", fund, {"balance": balance, "goal_progress": get_goal_progress(balance, goal_amount)}
	)


def format_amount(amount: float) -> str:
	"""*amount* in the site currency, which the desk also shows on Currency fields."""
	return fmt_money(amount, currency=frappe.db.get_default("currency"))


def show_fund_change(fund: str, message: str, amount: float) -> None:
	"""Show a short alert that *amount* went into or out of *fund*.

	*message* gets the fund as a link for {0} and the amount for {1}.
	"""
	label = frappe.db.get_value("Fund", fund, "fund")
	frappe.msgprint(
		message.format(get_link_to_form("Fund", fund, label), format_amount(amount)),
		alert=True,
		indicator="green",
	)


def warn_of_negative_balance(fund: str, message: str, change: float = 0) -> None:
	"""Warn in orange when *change* takes *fund* below zero.

	*message* gets the fund as a link for {0} and the balance after *change* for {1}.
	"""
	label, balance = frappe.db.get_value("Fund", fund, ["fund", "balance"])
	balance = (balance or 0) + change
	if balance < 0:
		frappe.msgprint(
			message.format(get_link_to_form("Fund", fund, label), format_amount(balance)),
			indicator="orange",
			title=_("Negative Fund Balance"),
		)


def get_give_path(fund: str, church: str | None) -> str:
	"""The /give address that chooses *fund*; it names *church* only on a multi-church site."""
	query = {"fund": fund}
	if church and is_multi_church():
		query = {"church": church, **query}

	return f"/give?{urlencode(query)}"


@frappe.whitelist(methods=["GET"])
def get_give_link(fund: str) -> dict:
	"""The /give address that chooses *fund*, and its QR code, for a printed card or an NFC tag. Reads only."""
	frappe.has_permission("Fund", "read", fund, throw=True)
	url = get_url(get_give_path(fund, frappe.db.get_value("Fund", fund, "church")))
	return {"url": url, "qr_code": get_qr_code(url)}
