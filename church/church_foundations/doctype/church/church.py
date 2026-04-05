# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet


class Church(NestedSet):
	nsm_parent_field = "parent_church"

	def before_save(self):
		if not self.parent_church:
			self.is_group = 1

	def on_trash(self):
		if not self.parent_church:
			frappe.throw(
				_(
					"The root church cannot be deleted. If you'd like to change it, "
					"please update the Church Name field instead."
				)
			)
		super().on_trash()

	def validate(self):
		if not self.parent_church:
			existing_root = frappe.db.get_value(
				"Church",
				{"parent_church": ("is", "not set"), "name": ("!=", self.name)},
				"name",
			)
			if existing_root:
				frappe.throw(
					_(
						"Only one root Church is allowed. '{0}' is already the root church. Please set a Parent Church."
					).format(existing_root)
				)
