# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils.nestedset import NestedSet


class ChurchLocation(NestedSet):
	def before_insert(self):
		# The tree view's Add Child names the parent after the doctype, not after nsm_parent_field.
		self.parent_location = self.parent_location or self.get("parent_church_location")

	def before_save(self):
		if not self.address and self.parent_location:
			self.address = frappe.db.get_value(self.doctype, self.parent_location, "address")
