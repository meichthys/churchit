import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form, nowdate

from churchit.church_finances.doctype.fund.fund import add_transaction, remove_transactions
from churchit.church_scope import (
	default_church,
	is_multi_church,
	refuse_another_churches_parent,
	refuse_another_churches_record,
)


class FundTransfer(Document):
	def before_save(self):
		fund_part = f"{self.from_fund or ''} to {self.to_fund or ''}".strip()
		parts = [fund_part, str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)

	def validate(self):
		if self.from_fund == self.to_fund:
			frappe.throw(_("Source and destination funds must be different."))
		if self.amount <= 0:
			frappe.throw(_("Transfer amount must be greater than zero."))
		self.set_church_when_the_source_is_shared()
		refuse_another_churches_parent(
			self, "from_fund", _("{0} belongs to another church, so only that church can move its money.")
		)
		# Money moves between funds, never between churches: both ends belong to
		# this church or are shared with every church.
		refuse_another_churches_record(self, "Fund", self.from_fund)
		refuse_another_churches_record(self, "Fund", self.to_fund)

	def set_church_when_the_source_is_shared(self):
		"""Keep a transfer out of a shared fund in the church that moves the money.

		`church` follows the source fund, and a shared fund's empty church would share the transfer
		with every church. A draft is fetched again on each save, so it keeps the church it has.
		"""
		if self.church or not is_multi_church():
			return
		before = self.get_doc_before_save()
		self.church = (before and before.church) or default_church()

	def on_submit(self):
		self.transfer_funds()

	def on_cancel(self):
		self.remove_fund_transfer_transactions()

	def transfer_funds(self):
		note = f": {self.notes}" if self.notes else ""
		rows = {
			self.from_fund: (-self.amount, f"Transfer to {self.to_fund}{note}"),
			self.to_fund: (self.amount, f"Transfer from {self.from_fund}{note}"),
		}
		for fund in sorted(rows):
			amount, fund_note = rows[fund]
			add_transaction(fund, amount, "Fund Transfer", self.name, self.date or nowdate(), notes=fund_note)

		from_label = frappe.db.get_value("Fund", self.from_fund, "fund")
		to_label = frappe.db.get_value("Fund", self.to_fund, "fund")
		frappe.msgprint(
			f"✅ Transferred ${self.amount} from "
			f"{get_link_to_form('Fund', self.from_fund, from_label)} to "
			f"{get_link_to_form('Fund', self.to_fund, to_label)}."
		)

	def remove_fund_transfer_transactions(self):
		from_label = frappe.db.get_value("Fund", self.from_fund, "fund") or self.from_fund
		to_label = frappe.db.get_value("Fund", self.to_fund, "fund") or self.to_fund

		remove_transactions("Fund Transfer", self.name)
		frappe.msgprint(
			f"⏪ Reverted transfer of ${self.amount} from "
			f"{get_link_to_form('Fund', self.from_fund, from_label)} to "
			f"{get_link_to_form('Fund', self.to_fund, to_label)}."
		)
