import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_link_to_form, nowdate

from churchit.church_finances.doctype.collection.collection import warn_of_unlikely_date
from churchit.church_finances.doctype.fund.fund import (
	add_transaction,
	format_amount,
	remove_transactions,
	warn_of_negative_balance,
)
from churchit.church_scope import (
	default_church,
	is_multi_church,
	refuse_another_churches_parent,
	refuse_another_churches_record,
)


class FundTransfer(Document):
	def before_save(self):
		self.title = get_title(self.from_fund, self.to_fund)

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
		if self.docstatus == 0 and self.from_fund:
			warn_of_negative_balance(
				self.from_fund,
				_("Submitting this transfer will reduce the {0} fund balance to {1}."),
				-self.amount,
			)
		warn_of_unlikely_date(self)

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
		from_label, to_label = get_fund_labels(self.from_fund, self.to_fund)
		note = f": {self.notes}" if self.notes else ""
		rows = {
			self.from_fund: (-self.amount, _("Transfer to {0}").format(to_label) + note),
			self.to_fund: (self.amount, _("Transfer from {0}").format(from_label) + note),
		}
		for fund in sorted(rows):
			amount, fund_note = rows[fund]
			add_transaction(fund, amount, "Fund Transfer", self.name, self.date or nowdate(), notes=fund_note)

		self.show_transfer(_("Moved {0} from {1} to {2}."))
		warn_of_negative_balance(self.from_fund, _("The {0} fund balance is now {1}."))

	def remove_fund_transfer_transactions(self):
		remove_transactions("Fund Transfer", self.name)
		self.show_transfer(_("Moved {0} back from {2} to {1}."))

	def show_transfer(self, message: str):
		"""Alert *message*, which gets the amount for {0} and the two funds as links for {1} and {2}."""
		from_label, to_label = get_fund_labels(self.from_fund, self.to_fund)
		frappe.msgprint(
			message.format(
				format_amount(self.amount),
				get_link_to_form("Fund", self.from_fund, from_label),
				get_link_to_form("Fund", self.to_fund, to_label),
			),
			alert=True,
			indicator="green",
		)


def get_fund_labels(from_fund: str, to_fund: str) -> tuple[str, str]:
	"""The names of the two funds, such as ('General', 'Building')."""
	names = dict(frappe.db.get_values("Fund", {"name": ("in", [from_fund, to_fund])}, ["name", "fund"]))
	return names.get(from_fund) or from_fund, names.get(to_fund) or to_fund


def get_title(from_fund: str, to_fund: str) -> str:
	"""'General to Building', from the names of the two funds."""
	from_label, to_label = get_fund_labels(from_fund, to_fund)
	return f"{from_label} to {to_label}"
