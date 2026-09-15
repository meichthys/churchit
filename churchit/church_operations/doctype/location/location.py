# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils.nestedset import NestedSet


class Location(NestedSet):
	def before_save(self):
		if not self.address and self.parent_location:
			self.address = frappe.db.get_value("Location", self.parent_location, "address")
