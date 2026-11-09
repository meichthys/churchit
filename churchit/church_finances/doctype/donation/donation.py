# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document


class Donation(Document):
	def after_insert(self):
		self.create_missionary_payment_if_needed()

	def on_update(self):
		self.create_missionary_payment_if_needed()

	def create_missionary_payment_if_needed(self):
		if self.missionary and self.status == "Paid":
			exists = frappe.db.exists("Missionary Payment", {"donation": self.name})
			if not exists:
				payment = frappe.get_doc({
					"doctype": "Missionary Payment",
					"donation": self.name,
					"missionary": self.missionary,
					"fund": self.fund,
					"amount": self.amount,
					"status": "Scheduled",
					"payment_date": frappe.utils.today()
				})
				payment.insert(ignore_permissions=True)
