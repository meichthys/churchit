# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet


class Location(NestedSet):
	def before_save(self):
		if not self.address and self.parent_location:
			self.address = frappe.db.get_value("Location", self.parent_location, "address")
