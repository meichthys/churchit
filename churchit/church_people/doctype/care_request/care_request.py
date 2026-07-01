# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CareRequest(Document):
	def before_insert(self):
		# Portal submissions don't capture Person — default it to the
		# logged-in user's linked Person record.
		if not self.person and frappe.session.user != "Guest":
			person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")
			if person:
				self.person = person

	def before_save(self):
		# If Assigned To is not set, pre-fill it from the person's current
		# care assignment (mirrors the client-side helper for non-portal entry).
		if self.person and not self.assigned_to:
			self.assigned_to = _current_deacon(self.person)


def _current_deacon(person):
	"""Return the deacon from the person's current care assignment, if any."""
	today = frappe.utils.nowdate()
	# An open-ended assignment (no end date) or one that has not yet ended.
	for filters in (
		{"person": person, "start_date": ["<=", today], "end_date": ["is", "not set"]},
		{"person": person, "start_date": ["<=", today], "end_date": [">=", today]},
	):
		deacon = frappe.db.get_value("Care Assignment", filters, "deacon", order_by="start_date desc")
		if deacon:
			return deacon
	return None
