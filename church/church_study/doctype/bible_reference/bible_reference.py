# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleReference(Document):
	pass

	def autoname(self):
		self.name = self.get_reference_name()

	def get_reference_name(self):
		"""Constructs the document name."""
		if self.start_verse and self.end_verse:
			ref = f"{self.start_verse} - {self.end_verse}"
		elif self.start_verse:
			ref = f"{self.start_verse}"
		else:
			frappe.throw("A start verse is required to name the reference")
		if self.translation:
			abbr = frappe.db.get_value("Bible Translation", self.translation, "abbreviation")
			ref = f"{ref} ({abbr})"
		return f"{self.church} - {ref}" if self.church else ref

	def on_update(self):
		new_name = self.get_reference_name()
		if not self.is_new() and self.name != new_name:
			frappe.rename_doc("Bible Reference", self.name, new_name)
