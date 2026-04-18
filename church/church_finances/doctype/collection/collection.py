# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Collection(Document):
	def before_save(self):
		parts = [self.function or "", str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)
		self.update_totals()

	def update_totals(self):
		# Recalculate entered total
		self.total_amount = sum(d.amount or 0 for d in self.donations)

		# Recalculate imbalance
		self.imbalance = (self.total_amount or 0) - (self.expected_total or 0)

		# Recalculate fund totals
		fund_totals = {}
		for donation in self.donations:
			if donation.fund and donation.amount:
				fund_totals.setdefault(donation.fund, 0)
				fund_totals[donation.fund] += donation.amount

		self.fund_totals = []
		for fund, total in fund_totals.items():
			self.append("fund_totals", {"fund": fund, "total": total})

		# Recalculate payment type totals
		payment_type_totals = {}
		for donation in self.donations:
			if donation.payment_type and donation.amount:
				payment_type_totals.setdefault(donation.payment_type, 0)
				payment_type_totals[donation.payment_type] += donation.amount

		self.payment_type_totals = []
		for payment_type, total in payment_type_totals.items():
			self.append("payment_type_totals", {"payment_type": payment_type, "total": total})

	def before_submit(self):
		if self.imbalance != 0:
			frappe.throw(
				f"Imbalance of {frappe.utils.fmt_money(self.imbalance)} must be resolved before submitting."
			)

	def on_submit(self):
		self.update_funds(reverse=False)

	def on_cancel(self):
		self.update_funds(reverse=True)

	def update_funds(self, reverse=False):
		fund_data = {}
		for donation in self.donations:
			if donation.fund and donation.amount:
				fund_data.setdefault(donation.fund, 0)
				fund_data[donation.fund] += donation.amount

		messages = []

		for fund_name, fund_total in fund_data.items():
			fund_doc = frappe.get_doc("Fund", fund_name)

			if reverse:
				fund_doc.transactions = [
					txn
					for txn in fund_doc.transactions
					if not (txn.source_type == "Collection" and txn.source == self.name)
				]
				fund_doc.balance = (fund_doc.balance or 0) - fund_total
				fund_doc.save(ignore_permissions=True)
				messages.append(f"💸 {fund_doc.fund} fund decreased by ${fund_total}")
			else:
				fund_doc.append(
					"transactions",
					{
						"amount": fund_total,
						"source_type": "Collection",
						"source": self.name,
						"date": frappe.utils.now(),
					},
				)
				fund_doc.balance = (fund_doc.balance or 0) + fund_total
				fund_doc.save(ignore_permissions=True)
				messages.append(f"💰 {fund_doc.fund} fund increased by ${fund_total}")
		if messages:
			frappe.msgprint("<br>".join(messages))
		# Warn if funds are now negative
		if fund_doc.balance < 0:
			frappe.msgprint(f"⚠️ {fund_doc.fund} fund balance is negative: {fund_doc.balance}")
