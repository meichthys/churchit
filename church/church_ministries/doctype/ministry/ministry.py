# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Ministry(Document):

	def validate(self):
		if self.end_date and self.start_date and self.end_date < self.start_date:
			frappe.throw("End Date cannot be before Start Date.")
