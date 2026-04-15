# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleReference(Document):
	def autoname(self):
		name = self.get_name()
		if not frappe.db.exists("Bible Reference", self.name):
			self.name = name
			return
		else:
			if self.name != self.get_name():
				frappe.rename_doc("Bible Reference", self.name, name)

	def get_name(self):
		"""Constructs the document name"""
		if self.start_verse and self.end_verse:
			ref = f"{self.start_verse} - {self.end_verse}"
		elif self.start_verse:
			ref = f"{self.start_verse}"
		else:
			frappe.throw("A start verse is required to name the reference")
		if self.translation:
			abbr = frappe.db.get_value("Bible Translation", self.translation, "abbreviation")
			return f"{ref} ({abbr})"
		else:
			return ref

	def on_update(self):
		# Rename document when updating
		self.autoname()

	def validate(self):
		self.reference = self.compute_reference()

	def compute_reference(self):
		start = frappe.db.get_value("Bible Verse", self.start_verse, "reference") if self.start_verse else ""
		end = frappe.db.get_value("Bible Verse", self.end_verse, "reference") if self.end_verse else ""
		abbr = frappe.db.get_value("Bible Translation", self.translation, "abbreviation")
		translation_text = f" ({abbr})" if abbr else ""
		end_verse_text = f" - {end}" if end and self.end_verse != self.start_verse else ""
		return f"{start}{end_verse_text}{translation_text}"
