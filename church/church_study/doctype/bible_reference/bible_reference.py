# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleReference(Document):
	pass

	def validate(self):
		self.reference = self.compute_reference()

	def compute_reference(self):
		# Determine the translation text to display based on the abbreviation of the Bible Translation
		abbr = frappe.db.get_value("Bible Translation", self.translation, "abbreviation")
		translation_text = f" ({abbr})" if abbr else ""
		end_verse_text = (
			f" - {self.end_verse}" if self.end_verse and self.end_verse != self.start_verse else ""
		)

		return f"{self.start_verse}{end_verse_text}{translation_text}"
