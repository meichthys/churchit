# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

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
