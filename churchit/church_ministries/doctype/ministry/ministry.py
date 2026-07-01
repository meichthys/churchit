# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Ministry(Document):

	def validate(self):
		if self.end_date and self.start_date and self.end_date < self.start_date:
			frappe.throw("End Date cannot be before Start Date.")
		self._refresh_recurring_functions()

	def onload(self):
		self._refresh_recurring_functions()

	def _refresh_recurring_functions(self):
		"""Populate `recurring_functions` with any Function template (auto_repeat=1)
		whose `associated_ministry` points at this Ministry."""
		self.set("recurring_functions", [])
		if not self.name or self.is_new():
			return

		templates = frappe.get_all(
			"Function",
			filters={"associated_ministry": self.name, "auto_repeat": 1},
			fields=["name", "repeat_frequency"],
			order_by="function_name asc",
		)
		for tpl in templates:
			self.append("recurring_functions", {
				"function": tpl.name,
				"repeat_frequency": tpl.repeat_frequency,
			})
