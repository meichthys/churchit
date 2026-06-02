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


@frappe.whitelist()
def create_email_group(group):
	"""Create (or top up) a Frappe Email Group from this Person Group's members.

	Pulls each member's Person.email into an Email Group named after the group so
	the group can be used as a newsletter recipient list. Idempotent — the unique
	(email_group, email) index means re-running just adds any new members.
	"""
	from frappe.email.doctype.email_group.email_group import add_subscribers

	doc = frappe.get_doc("Group", group)
	email_group = doc.group_name or doc.name

	created = False
	if not frappe.db.exists("Email Group", email_group):
		frappe.get_doc({"doctype": "Email Group", "title": email_group}).insert(
			ignore_permissions=True
		)
		created = True

	person_ids = [m.person for m in doc.members if m.person]
	emails, missing = [], []
	if person_ids:
		for row in frappe.get_all(
			"Person",
			filters={"name": ["in", person_ids]},
			fields=["name", "full_name", "email"],
		):
			if row.email:
				emails.append(row.email)
			else:
				missing.append(row.full_name or row.name)

	if emails:
		add_subscribers(email_group, emails)

	return {
		"email_group": email_group,
		"created": created,
		"emails_synced": len(emails),
		"missing": missing,
		"total_members": frappe.db.count("Email Group Member", {"email_group": email_group}),
	}
