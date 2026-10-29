# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.group_leaders import require_leader
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import refuse_another_churches_parent


class GroupFile(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "group", _("{0} belongs to another church, so only that church can add files to it.")
		)
		# The group-files web form saves with ignore_permissions, so this runs for every member save.
		if is_portal_member():
			require_leader(self.group)
		if (self.attached_file or "").startswith("/files/"):
			frappe.throw(_("Upload the file as private, so that only the group's members can open it."))
		if self.has_value_changed("attached_file"):
			self.refuse_unreadable_private_file()

	def refuse_unreadable_private_file(self):
		"""Frappe attaches an unattached File by its URL with no permission check, so check it here."""
		if not (self.attached_file or "").startswith("/private/files/"):
			return

		files = frappe.get_all("File", {"file_url": self.attached_file}, pluck="name")
		if not any(frappe.get_doc("File", name).is_downloadable() for name in files):
			frappe.throw(_("You cannot attach a file that you cannot open."), frappe.PermissionError)
