# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	add_years,
	flt,
	fmt_money,
	formatdate,
	get_first_day_of_week,
	getdate,
	now,
	today,
)

from churchit.church_finances.doctype.fund.fund import (
	add_transaction,
	format_amount,
	remove_transactions,
	show_fund_change,
	warn_of_negative_balance,
)
from churchit.church_finances.doctype.giving_settings.giving_settings import get_currency
from churchit.church_foundations.doctype.church.church import church_name
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_scope import refuse_another_churches_record
from churchit.church_summary.metrics import record_week
from churchit.contacts import get_primary_emails
from churchit.utils import LONG_DATE_FORMAT, get_dated_title

# Payment Type of the money a gateway takes (created in after_install / patch).
ONLINE_PAYMENT_TYPE = "Online"


class Collection(Document):
	def onload(self):
		self.set_onload("email_receipts", frappe.db.get_single_value("Giving Settings", "email_receipts"))

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
		warn_of_unlikely_date(self)
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
		function_name = self.function and frappe.db.get_value("Function", self.function, "function_name")
		self.title = get_title(function_name, self.date)
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

	def send_receipts(self):
		"""Email each giver one receipt with their total, while Giving Settings asks for it.

		An online gift sends its own receipt and an imported batch sends none.
		"""
		if self.flags.skip_receipts or self.import_batch:
			return
		if not frappe.db.get_single_value("Giving Settings", "email_receipts") or not can_send_email():
			return

		gifts = {}
		for donation in self.donations:
			if donation.person_email and flt(donation.amount) > 0:
				gifts.setdefault(donation.person_email, []).append(donation)

		template = frappe.get_doc("Email Template", "Donation Acknowledgment")
		for email, donations in gifts.items():
			funds = dict.fromkeys(
				frappe.get_cached_value("Fund", row.fund, "fund") or row.fund for row in donations
			)
			first_name = frappe.db.get_value("Person", donations[0].person, "first_name")
			message = template.get_formatted_email(
				{
					"first_name": first_name or _("Friend"),
					"amount": fmt_money(sum(flt(row.amount) for row in donations), currency=get_currency()),
					"fund": ", ".join(funds),
					"date": formatdate(self.date, LONG_DATE_FORMAT),
					"church_name": church_name(self) or "",
					"doc": self,
				}
			)
			frappe.sendmail(
				recipients=[email],
				subject=message["subject"],
				message=message["message"],
				reference_doctype=self.doctype,
				reference_name=self.name,
			)

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
				_("Resolve the imbalance of {0} before you submit.").format(format_amount(self.imbalance))
			)

	def on_submit(self):
		self.update_funds(reverse=False)
		self.recount_old_week()
		self.send_receipts()

	def on_cancel(self):
		# Finance cancels a gift's Collection after a refund at the processor. The gifts
		# are locked one by one before the Funds, in the order record_charge locks them.
		# church-scope: the gifts this Collection recorded, which its own cancel check allowed
		gifts = frappe.get_all("Online Donation", {"collection": self.name, "status": "Paid"}, pluck="name")
		for gift in gifts:
			frappe.db.set_value("Online Donation", gift, "status", "Refunded")

		self.update_funds(reverse=True)
		self.recount_old_week()

	def update_funds(self, reverse=False):
		"""Add or remove the ledger rows of each fund, and tell the user how each fund changed.

		Only money going out warns of a negative balance. An online gift sets `flags.hide_fund_messages`,
		so its giver never sees the church's fund balances.
		"""
		fund_totals = {}
		for donation in self.donations:
			if donation.fund and donation.amount:
				fund_totals[donation.fund] = fund_totals.get(donation.fund, 0) + donation.amount

		if reverse:
			remove_transactions("Collection", self.name)

		for fund, total in sorted(fund_totals.items()):
			if not reverse:
				add_transaction(fund, total, "Collection", self.name, self.date)
			change = flt(-total if reverse else total, self.precision("total_amount"))
			if self.flags.hide_fund_messages or not change:
				continue
			if change > 0:
				show_fund_change(fund, _("{0} fund increased by {1}"), change)
			else:
				show_fund_change(fund, _("{0} fund decreased by {1}"), -change)
				warn_of_negative_balance(fund, _("The {0} fund balance is now {1}."))

	def recount_old_week(self):
		"""Queue a recount of the Weekly Metrics of this collection's week, when the daily job no longer recounts it.

		The daily job recounts this week and last week. `record_week` writes every church's row, so one
		job for each week is enough, and it keeps two jobs from adding the same row.
		"""
		week_start = get_first_day_of_week(getdate(self.date))
		if week_start >= add_days(get_first_day_of_week(today()), -7):
			return
		frappe.enqueue(
			record_week,
			week_start=week_start,
			job_id=f"weekly_metrics_{week_start}",
			deduplicate=True,
			enqueue_after_commit=True,
		)


def warn_of_unlikely_date(doc: Document) -> None:
	"""Warn in orange when a person sets a money record's date more than 30 days ahead or more than a year back.

	A typo year still changes the fund balances, and the money then misses its statement and this
	month's reports. Back-entry stays possible, so this only warns. An import or a save by code says nothing.
	"""
	if (
		frappe.flags.in_import
		or doc.flags.ignore_permissions
		or not doc.date
		or not doc.has_value_changed("date")
	):
		return
	date = getdate(doc.date)
	if date > add_days(getdate(), 30):
		message = _("The date {0} is more than 30 days after today.")
	elif date < add_years(getdate(), -1):
		message = _("The date {0} is more than a year before today.")
	else:
		return
	frappe.msgprint(message.format(formatdate(date)), indicator="orange", title=_("Check the Date"))


def get_title(function_name: str | None, date: str | datetime) -> str:
	"""The Function's name and the long date, such as "Sunday Worship, Tuesday, October 20, 2026"."""
	return get_dated_title(function_name or _("Collection"), date)


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
	collection.flags.hide_fund_messages = True
	collection.flags.skip_receipts = True
	collection.insert(ignore_permissions=True)
	collection.submit()
	return collection.name
