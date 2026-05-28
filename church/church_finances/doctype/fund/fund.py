# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Fund(Document):
	def before_save(self):
		# Ensure balance is always current before saving
		self.recalculate_balance()

	def recalculate_balance(self):
		# Calculate balance from all financial transactions
		total_balance = 0
		for transaction in self.transactions:
			total_balance += transaction.amount or 0

		# Update the balance field
		self.balance = total_balance
