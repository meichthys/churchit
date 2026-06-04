# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class Expense(Document):
	def validate(self):
		if self.type:
			self.associated_fund = frappe.db.get_value("Expense Type", self.type, "fund")
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
				f"⚠️ Submitting this expense will reduce the "
				f"{get_link_to_form('Fund', fund_name, label=fund.fund)} "
				f"fund balance to ${projected_balance:,.2f}.",
				indicator="orange",
				title="Negative Fund Balance",
			)

	def before_delete(self):
		# This probably should never get called since frappe prevents the deletion
		# of submitted documents by default, but just to be sure we'll provide our own warning.
		# Prevent deletion if the document is not cancelled
		if not self.docstatus == 2:  # 2 is Cancelled
			frappe.throw("❌ You must cancel this Expense before deleting it.")

	def on_cancel(self):
		fund_name = frappe.db.get_value("Expense Type", self.type, "fund")
		if not fund_name:
			frappe.throw("⚠️ No fund linked to the selected Expense Type.")

		fund = frappe.get_doc("Fund", fund_name)

		# Remove transaction that matches this expense
		updated_transactions = []
		for transaction in fund.transactions:
			if not (transaction.source_type == "Expense" and transaction.source == self.name):
				updated_transactions.append(transaction)
			else:
				frappe.msgprint(
					f"💰 Associated {get_link_to_form('Fund', fund.fund)} fund has been increased by ${-transaction.amount}"
				)
		fund.transactions = updated_transactions
		fund.save(ignore_permissions=True)
		fund.reload()

		if self.ministry:
			_update_ministry_total(self.ministry)

	def on_submit(self):
		# Get related Fund via Expense Type
		fund_name = frappe.db.get_value("Expense Type", self.type, "fund")

		if not fund_name:
			frappe.throw("⚠️ No fund linked to the selected Expense Type.")

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
			f"💸 Associated {get_link_to_form('Fund', fund.fund)} fund has been reduced by ${self.amount}"
		)

		if self.ministry:
			_update_ministry_total(self.ministry)


def _update_ministry_total(ministry_name):
	total = frappe.db.sql(
		"SELECT COALESCE(SUM(amount), 0) FROM `tabExpense` WHERE ministry = %s AND docstatus = 1",
		ministry_name,
	)[0][0]
	frappe.db.set_value("Ministry", ministry_name, "total_expenses", total)
