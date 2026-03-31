# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Prayer(Document):
	def before_save(self):
		self.title = self.person or ""
