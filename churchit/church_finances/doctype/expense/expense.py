# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce, Sum
from frappe.utils import flt

from churchit.church_finances.doctype.collection.collection import warn_of_unlikely_date
from churchit.church_finances.doctype.fund.fund import (
	add_transaction,
	remove_transactions,
	show_fund_change,
	warn_of_negative_balance,
)
from churchit.church_scope import refuse_another_churches_record


class Expense(Document):
	def validate(self):
		# A negative expense would add money to the fund.
		if flt(self.amount) <= 0:
			frappe.throw(_("Enter the amount paid. To undo an expense, cancel it."))
		if self.type:
			self.associated_fund = frappe.db.get_value("Expense Type", self.type, "fund")
		# An Expense Type is shared by every church, so the fund it names may not be.
		refuse_another_churches_record(self, "Fund", self.associated_fund)
		self._warn_if_fund_would_go_negative()
		warn_of_unlikely_date(self)

	def _warn_if_fund_would_go_negative(self):
		if self.docstatus != 0 or not self.associated_fund or not self.amount:
			return
		warn_of_negative_balance(
			self.associated_fund,
			_("Submitting this expense will reduce the {0} fund balance to {1}."),
			-self.amount,
		)

	def on_trash(self):
		# A submitted Expense is still reducing its Fund balance, so it has to be
		# cancelled first. A draft never touched the balance.
		if self.docstatus == 1:
			frappe.throw(_("Cancel this expense before you delete it."))

	def on_cancel(self):
		for fund_name in remove_transactions("Expense", self.name):
			show_fund_change(fund_name, _("{0} fund increased by {1}"), self.amount)

		if self.ministry:
			_update_ministry_total(self.ministry)

		self.move_alms_requests(self.name, "Distributed", "Approved")

	def move_alms_requests(self, expense: str, from_status: str, to_status: str):
		"""Link the Alms Requests that *expense* paid to this expense, and set a *from_status* one to *to_status*.

		A cancel keeps the link, so the amended copy takes the requests over and Create Expense does not
		pay them a second time.
		"""
		# church-scope: the requests that this expense, or the expense it amends, paid
		for request in frappe.get_all("Alms Request", {"associated_expense": expense}, ["name", "status"]):
			values = {"associated_expense": self.name}
			if request.status == from_status:
				values["status"] = to_status
			frappe.db.set_value("Alms Request", request.name, values)

	def on_submit(self):
		fund_name = self.associated_fund

		if not fund_name:
			frappe.throw(_("The Expense Type {0} has no fund. Set its Fund first.").format(self.type))

		add_transaction(fund_name, -self.amount, "Expense", self.name, self.date, notes=self.notes)
		show_fund_change(fund_name, _("{0} fund decreased by {1}"), self.amount)
		warn_of_negative_balance(fund_name, _("The {0} fund balance is now {1}."))

		if self.ministry:
			_update_ministry_total(self.ministry)

		if self.amended_from:
			self.move_alms_requests(self.amended_from, "Approved", "Distributed")


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
