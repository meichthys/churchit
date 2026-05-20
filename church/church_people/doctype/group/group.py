# Copyright (c) 2026, meichthys and contributors
# License: MIT.

import frappe
from frappe.model.document import Document


class Group(Document):
	def has_webform_permission(self):
		"""Portal access: only members of a portal-visible group may view it."""
		if not self.show_in_portal:
			return False
		user = frappe.session.user
		if user == "Guest":
			return False
		person = frappe.db.get_value("Person", {"user": user}, "name")
		if not person:
			return False
		return bool(
			frappe.db.exists("Group Member", {"parent": self.name, "person": person})
		)
