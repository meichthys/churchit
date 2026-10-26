# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from churchit.church_finances.doctype.fund.fund import add_transaction, remove_transactions
from churchit.church_scope import refuse_another_churches_record
from churchit.contacts import get_primary_emails

# Payment Type of the money a gateway takes (created in after_install / patch).
ONLINE_PAYMENT_TYPE = "Online"


class Collection(Document):
	def before_insert(self):
		# Its cancel marked the gift Refunded, so an amended copy would count a gift with no record.
		# church-scope: the gifts of the Collection this one amends, which the user could cancel
		if self.amended_from and frappe.db.exists("Online Donation", {"collection": self.amended_from}):
			frappe.throw(
				_(
					"Collection {0} recorded an online gift, so it cannot be amended. To correct it, make a new collection with a negative donation row."
				).format(self.amended_from)
			)

	def validate(self):
		for donation in self.donations:
			refuse_another_churches_record(self, "Fund", donation.fund)
			# Statements describe donated property and never value it (IRS Publication 1771).
			if donation.is_non_cash and (donation.amount or not (donation.description or "").strip()):
				frappe.throw(
					_(
						"Row {0}: a non-cash gift needs a description of what was given, and an amount of 0."
					).format(donation.idx)
				)

	def before_save(self):
		parts = [self.function or "", str(self.date or "")]
		self.title = " - ".join(p for p in parts if p)
		self.update_totals()
		self.set_donor_emails()

	def set_donor_emails(self):
		"""Copy each giver's primary email onto their Donation row.

		The Donation Acknowledgment notification reads ``person_email`` off the
		rows it walks. This used to be a ``fetch_from`` on ``person.email``, which
		stopped working when emails moved to a child table, because Frappe can
		fetch across a Link but not into the linked record's own child rows.
		"""
		people = [d.person for d in self.donations if d.person]
		by_person = get_primary_emails("Person", people)
		for donation in self.donations:
			donation.person_email = by_person.get(donation.person) if donation.person else None

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
		# Finance cancels a gift's Collection after a refund at the processor. The gifts
		# are locked one by one before the Funds, in the order record_charge locks them.
		# church-scope: the gifts this Collection recorded, which its own cancel check allowed
		gifts = frappe.get_all("Online Donation", {"collection": self.name, "status": "Paid"}, pluck="name")
		for gift in gifts:
			frappe.db.set_value("Online Donation", gift, "status", "Refunded")

		self.update_funds(reverse=True)

	def update_funds(self, reverse=False):
		fund_totals = {}
		for donation in self.donations:
			if donation.fund and donation.amount:
				fund_totals[donation.fund] = fund_totals.get(donation.fund, 0) + donation.amount

		if reverse:
			remove_transactions("Collection", self.name)

		messages = []
		for fund, total in sorted(fund_totals.items()):
			if not reverse:
				add_transaction(fund, total, "Collection", self.name, self.date)
			label, balance = frappe.db.get_value("Fund", fund, ["fund", "balance"])
			messages.append(
				f"💸 {label} fund decreased by ${total}"
				if reverse
				else f"💰 {label} fund increased by ${total}"
			)
			if balance < 0:
				messages.append(f"⚠️ {label} fund balance is negative: {balance}")

		if messages:
			frappe.msgprint("<br>".join(messages))


def add_single_donation(church: str, fund: str, amount: float, notes: str, person: str | None = None) -> str:
	"""Record one online payment as a submitted Collection of one Donation row, and return its name.

	The payment settles the church, not the session: a gateway calls back with whatever session finished
	the payment, and a shared fund names no church. A row with no *person* is on no Giving Statement.
	"""
	collection = frappe.new_doc("Collection")
	collection.date = now()
	collection.church = church
	collection.append(
		"donations",
		{
			"amount": amount,
			"payment_type": ONLINE_PAYMENT_TYPE,
			"fund": fund,
			"person": person or None,
			"notes": notes,
		},
	)
	# A single-donation collection balances exactly, so before_submit() passes.
	collection.expected_total = amount
	collection.insert(ignore_permissions=True)
	collection.submit()
	return collection.name
