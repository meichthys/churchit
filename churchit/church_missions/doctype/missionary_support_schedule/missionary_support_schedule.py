# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


class MissionarySupportSchedule(Document):
	def validate(self):
		if self.monthly_amount and self.monthly_amount < 0:
			frappe.throw(_("Monthly Amount cannot be negative."))

		if self.end_date and self.start_date and getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("End Date cannot be before Start Date."))

		self._calculate_total_committed()

	def _calculate_total_committed(self):
		"""Calculate total committed amount based on monthly amount and date range."""
		if not self.monthly_amount or not self.start_date:
			self.total_committed = 0
			return

		start = getdate(self.start_date)
		end = getdate(self.end_date) if self.end_date else getdate(today())

		if end < start:
			self.total_committed = 0
			return

		# Calculate number of months (inclusive of start month)
		months = (end.year - start.year) * 12 + (end.month - start.month) + 1
		self.total_committed = flt(self.monthly_amount) * months

	@frappe.whitelist()
	def get_received_to_date(self):
		"""Get total donations received for this missionary from the fund."""
		if not self.missionary:
			return 0

		# Get the missionary's fund
		fund_name = f"Missionary: {frappe.db.get_value('Missionary', self.missionary, 'title')}"
		if not frappe.db.exists("Fund", fund_name):
			return 0

		# Sum all donations to this fund
		from churchit.church_finances.doctype.donation.donation import Donation
		from churchit.church_scope import church_filters

		donations = frappe.get_all(
			"Donation",
			filters=church_filters(frappe.get_cached_doc("Fund", fund_name).church, {"fund": fund_name}),
			fields=["amount"],
		)
		return sum(flt(d.amount) for d in donations)

	@frappe.whitelist()
	def get_balance(self):
		"""Get the balance (committed - received)."""
		committed = flt(self.total_committed)
		received = flt(self.get_received_to_date())
		return committed - received

	@frappe.whitelist()
	def get_last_payment_date(self):
		"""Get the date of the last donation to this missionary's fund."""
		if not self.missionary:
			return None

		fund_name = f"Missionary: {frappe.db.get_value('Missionary', self.missionary, 'title')}"
		if not frappe.db.exists("Fund", fund_name):
			return None

		from churchit.church_scope import church_filters

		donation = frappe.get_all(
			"Donation",
			filters=church_filters(frappe.get_cached_doc("Fund", fund_name).church, {"fund": fund_name}),
			fields=["creation"],
			order_by="creation desc",
			limit=1,
		)
		return donation[0].creation if donation else None

	@frappe.whitelist()
	def get_next_due_date(self):
		"""Get the next due date based on the schedule."""
		if not self.monthly_amount or not self.start_date:
			return None

		from frappe.utils import add_months, getdate

		start = getdate(self.start_date)
		today_date = getdate(today())

		if today_date < start:
			return start

		# Find the next month after the last completed month
		months_passed = (today_date.year - start.year) * 12 + (today_date.month - start.month)
		next_due = add_months(start, months_passed + 1)

		if self.end_date and getdate(next_due) > getdate(self.end_date):
			return None

		return next_due
