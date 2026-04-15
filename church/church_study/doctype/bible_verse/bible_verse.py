# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleVerse(Document):
	def autoname(self):
		self.name = self.get_name()

	def get_name(self):
		"""Constructs the document name"""
		return f"{self.book} {self.chapter}:{self.verse}"

	def before_save(self):
		book_name = frappe.db.get_value("Bible Book", self.book, "book") if self.book else ""
		self.reference = f"{book_name} {self.chapter}:{self.verse}"
		if not self.is_new():
			new_name = self.get_name()
			if self.name != new_name:
				frappe.rename_doc("Bible Verse", self.name, new_name, force=True)
				self.name = new_name
