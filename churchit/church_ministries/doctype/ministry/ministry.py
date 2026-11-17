# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.unique_names import refuse_a_second_with_this_name


class Ministry(Document):
	def validate(self):
		refuse_a_second_with_this_name(
			self,
			"ministry_name",
			_("There is already a ministry called {0}. Give this ministry another name."),
		)
		if self.end_date and self.start_date and self.end_date < self.start_date:
			frappe.throw(_("End Date cannot be before Start Date."))
		self._refresh_recurring_functions()

	def onload(self):
		self._refresh_recurring_functions()

	def _refresh_recurring_functions(self):
		"""Populate `recurring_functions` with any Function template (auto_repeat=1)
		whose `associated_ministry` points at this Ministry."""
		self.set("recurring_functions", [])
		if not self.name or self.is_new():
			return

		# church-scope: the recurring functions of this one ministry
		templates = frappe.get_all(
			"Function",
			filters={"associated_ministry": self.name, "auto_repeat": 1},
			fields=["name", "repeat_frequency"],
			order_by="function_name asc",
		)
		for tpl in templates:
			self.append(
				"recurring_functions",
				{
					"function": tpl.name,
					"repeat_frequency": tpl.repeat_frequency,
				},
			)
