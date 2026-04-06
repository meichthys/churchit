# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleVerse(Document):
	def before_save(self):
		book_name = frappe.db.get_value("Bible Book", self.book, "book") if self.book else ""
		self.reference = f"{book_name} {self.chapter}:{self.verse}"
