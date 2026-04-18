# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form


class Expense(Document):
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
