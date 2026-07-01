# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Fund(Document):
	def before_save(self):
		# Ensure balance and goal progress are always current before saving
		self.recalculate_balance()
		self.update_goal_progress()

	def recalculate_balance(self):
		# Calculate balance from all financial transactions
		total_balance = 0
		for transaction in self.transactions:
			total_balance += transaction.amount or 0

		# Update the balance field
		self.balance = total_balance

	def update_goal_progress(self):
		# Percentage of the goal amount reached by the current balance.
		if self.goal_amount and self.goal_amount > 0:
			self.goal_progress = (self.balance or 0) / self.goal_amount * 100
		else:
			self.goal_progress = 0
