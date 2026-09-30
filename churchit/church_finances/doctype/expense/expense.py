# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import get_link_to_form

from churchit.church_scope import refuse_another_churches_record


class Expense(Document):
	def validate(self):
		if self.type:
			self.associated_fund = frappe.db.get_value("Expense Type", self.type, "fund")
		# An Expense Type is shared by every church, so the fund it names may not be.
		refuse_another_churches_record(self, "Fund", self.associated_fund)
		self._warn_if_fund_would_go_negative()

	def _warn_if_fund_would_go_negative(self):
		if self.docstatus != 0 or not self.type or not self.amount:
			return
		fund_name = frappe.db.get_value("Expense Type", self.type, "fund")
		if not fund_name:
			return
		fund = frappe.db.get_value("Fund", fund_name, ["fund", "balance"], as_dict=True)
		if not fund:
			return
		projected_balance = (fund.balance or 0) - self.amount
		if projected_balance < 0:
			frappe.msgprint(
				_("⚠️ Submitting this expense will reduce the {0} fund balance to {1}.").format(
					get_link_to_form("Fund", fund_name, label=fund.fund), f"${projected_balance:,.2f}"
				),
				indicator="orange",
				title=_("Negative Fund Balance"),
			)

	def on_trash(self):
		# A submitted Expense is still reducing its Fund balance, so it has to be
		# cancelled first. A draft never touched the balance.
		if self.docstatus == 1:
			frappe.throw(_("❌ You must cancel this Expense before deleting it."))

	def on_cancel(self):
		# The fund this expense debited, even if its type names another one by now.
		fund_name = self.associated_fund or frappe.db.get_value("Expense Type", self.type, "fund")
		if not fund_name:
			frappe.throw(_("⚠️ No fund linked to the selected Expense Type."))

		fund = frappe.get_doc("Fund", fund_name)

		# Remove transaction that matches this expense
		updated_transactions = []
		for transaction in fund.transactions:
			if not (transaction.source_type == "Expense" and transaction.source == self.name):
				updated_transactions.append(transaction)
			else:
				frappe.msgprint(
					f"💰 Associated {get_link_to_form('Fund', fund.name, fund.fund)} fund has been increased by ${-transaction.amount}"
				)
		fund.transactions = updated_transactions
		fund.save(ignore_permissions=True)
		fund.reload()

		if self.ministry:
			_update_ministry_total(self.ministry)

	def on_submit(self):
		fund_name = self.associated_fund

		if not fund_name:
			frappe.throw(_("⚠️ No fund linked to the selected Expense Type."))

		fund = frappe.get_doc("Fund", fund_name)

		# Add new row to fund's transactions table
		fund.append(
			"transactions",
			{
				"amount": -self.amount,
				"source_type": "Expense",
				"source": self.name,
				"date": self.date,
				"notes": self.notes,
			},
		)
		fund.save(ignore_permissions=True)
		fund.reload()
		frappe.msgprint(
			f"💸 Associated {get_link_to_form('Fund', fund.name, fund.fund)} fund has been reduced by ${self.amount}"
		)

		if self.ministry:
			_update_ministry_total(self.ministry)


def _update_ministry_total(ministry_name):
	# church-scope: every expense booked against this ministry. A ministry shared with
	# every church holds the joint figure on purpose; per-church spending comes from
	# the Expense rows, which each keep their own church.
	Expense = frappe.qb.DocType("Expense")
	total = (
		frappe.qb.from_(Expense)
		.select(Coalesce(Sum(Expense.amount), 0))
		.where((Expense.ministry == ministry_name) & (Expense.docstatus == 1))
		.run()[0][0]
	)
	frappe.db.set_value("Ministry", ministry_name, "total_expenses", total)
