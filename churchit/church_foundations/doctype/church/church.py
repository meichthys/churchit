# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class Church(NestedSet):
	nsm_parent_field = "parent_church"

	def validate(self):
		existing = frappe.db.get_value("Church", {"name": ("!=", self.name)}, "name")
		if existing:
			frappe.throw(
				_(
					"Only one Church record is allowed. "
					"Multi-church support may be added in a future release."
				)
			)

	def on_trash(self):
		frappe.throw(_("The Church record cannot be deleted."))
