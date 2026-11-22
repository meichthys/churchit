# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

from churchit.church_people.group_leaders import require_leader
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import refuse_another_churches_parent
from churchit.portal.realtime import notify_person
from churchit.utils import validate_https_url

PRIVATE_FILES = "/private/files/"


def is_web_link(url: str) -> bool:
	"""Whether *url* names a page elsewhere (any scheme, or //host) rather than a path on this site."""
	return "://" in url or url.startswith("//") or ":" in url.split("/", 1)[0]


class GroupFile(Document):
	def validate(self):
		refuse_another_churches_parent(
			self, "group", _("{0} belongs to another church, so only that church can add files to it.")
		)
		# The group-files web form saves with ignore_permissions, so this runs for every member save.
		if is_portal_member():
			require_leader(self.group)
		if not self.attached_file:
			return
		if is_web_link(self.attached_file):
			# A link to a file elsewhere, such as a shared document, as the group files form has always taken.
			self.attached_file = validate_https_url(self.attached_file, "link")
		elif not self.attached_file.startswith(PRIVATE_FILES):
			frappe.throw(_("Upload the file as private, so that only the group's members can open it."))
		elif self.has_value_changed("attached_file"):
			self.refuse_unreadable_private_file()

	def refuse_unreadable_private_file(self):
		"""Frappe attaches an unattached File by its URL with no permission check, so check it here."""
		files = frappe.get_all("File", {"file_url": self.attached_file}, pluck="name")
		if not any(frappe.get_doc("File", name).is_downloadable() for name in files):
			frappe.throw(_("You cannot attach a file that you cannot open."), frappe.PermissionError)

	def after_insert(self):
		# church-scope: the member rows of the file's own group
		for person in frappe.get_all(
			"Group Member", {"parenttype": "Group", "parent": self.group}, pluck="person", distinct=True
		):
			notify_person(person, "group-files", self.name)
