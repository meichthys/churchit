# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleVerse(Document):
	pass

	def autoname(self):
		self.name = self.get_verse_name()

	def get_verse_name(self):
		"""Constructs the document name."""
		return f"{self.church} - {self.book} {self.chapter}:{self.verse}"

	def before_save(self):
		if not self.is_new():
			new_name = self.get_verse_name()
			if self.name != new_name:
				frappe.rename_doc("Bible Verse", self.name, new_name, force=True)
				self.name = new_name
