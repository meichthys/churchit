# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from churchit.church_people.doctype.background_check.background_check import is_cleared
from churchit.church_scope import refuse_another_churches_parent


class MinistryTeamPosition(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "ministry", _("{0} belongs to another church, so only that church can add positions to it.")
		)
		ministry_name = frappe.db.get_value("Ministry", self.ministry, "ministry_name")
		self.title = f"{self.position_name} ({ministry_name})"
		self.warn_about_people_without_checks()

	def warn_about_people_without_checks(self):
		"""Warn, never refuse: a person often joins the roster while their check is still in progress."""
		if not self.needs_background_check:
			return
		previous = self.get_doc_before_save()
		known = {row.person for row in previous.people} if previous else set()
		required = [row.check_type for row in self.required_checks]
		lacking = [
			frappe.db.get_value("Person", row.person, "full_name")
			for row in self.people
			if row.person not in known and not is_cleared(row.person, nowdate(), required)
		]
		if lacking:
			frappe.msgprint(
				_("These people do not have the current, cleared checks this position needs: {0}.").format(
					", ".join(lacking)
				),
				title=_("Checks needed"),
				indicator="orange",
			)
