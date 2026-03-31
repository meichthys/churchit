# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class BibleVerse(Document):
	def before_save(self):
		self.title = f"{self.book} {self.chapter}:{self.verse}"
