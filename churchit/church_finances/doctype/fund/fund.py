# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe.model.document import Document
from frappe.query_builder.functions import Max
from frappe.utils import flt, get_url
from frappe.utils.print_format_generator import get_qr_code

from churchit.church_scope import is_multi_church


class Fund(Document):
	def before_save(self):
		self.recalculate_balance()
		self.update_goal_progress()

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


@frappe.whitelist()
def get_give_link(fund: str) -> dict:
	"""The /give address that chooses *fund*, and its QR code, for a printed card or an NFC tag."""
	frappe.has_permission("Fund", "read", fund, throw=True)
	query = {"fund": fund}
	church = frappe.db.get_value("Fund", fund, "church")
	if church and is_multi_church():
		query = {"church": church, **query}

	url = get_url(f"/give?{urlencode(query)}")
	return {"url": url, "qr_code": get_qr_code(url)}
