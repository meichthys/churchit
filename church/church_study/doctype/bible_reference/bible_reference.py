# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleReference(Document):
	def before_save(self):
		if self.start_verse and self.end_verse:
			ref = f"{self.start_verse} - {self.end_verse}"
		elif self.start_verse:
			ref = str(self.start_verse)
		else:
			ref = ""
		if self.translation:
			abbr = frappe.db.get_value("Bible Translation", self.translation, "abbreviation")
			self.title = f"{ref} ({abbr})"
		else:
			self.title = ref
