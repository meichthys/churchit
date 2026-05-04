# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class FunctionSignUpItem(Document):
	def validate(self):
		# When this row belongs to a Function Sign-Up, mirror the function-level
		# quantity_needed for display.
		if self.parenttype != "Function Sign-Up" or not self.item:
			return
		function = frappe.db.get_value("Function Sign-Up", self.parent, "function")
		if not function:
			return
		qty_needed = frappe.db.get_value(
			"Function Sign-Up Item",
			{"parent": function, "parenttype": "Function", "item": self.item},
			"quantity_needed",
		)
		self.quantity_needed = qty_needed or 0
