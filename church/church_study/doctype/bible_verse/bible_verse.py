# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BibleVerse(Document):
	pass

	def validate(self):
		self.reference = self.calculate_name()

	def calculate_name(self):
		"""Constructs the document name"""
		return f"{self.book} {self.chapter}:{self.verse}"
