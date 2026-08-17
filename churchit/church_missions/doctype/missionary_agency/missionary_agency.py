# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from churchit.contacts import validate_contact_tables


class MissionaryAgency(Document):
	def validate(self):
		validate_contact_tables(self)
