# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from churchit.church_foundations.church_access import has_every_church

GENERAL = "General"
PASTORAL_CARE = "Pastoral Care"
BENEVOLENCE = "Benevolence"
PASTORAL_ROLES = ("Church Pastoral Care", "Church Manager")


class NoteCategory(Document):
	"""A kind of note about a person, with the roles that read and add it. A blank list leaves it to everyone."""

	def validate(self):
		if self.is_new() or self.access != self.get_doc_before_save().access:
			self.refuse_unless_every_church()

	def on_trash(self):
		self.refuse_unless_every_church()

	@property
	def access(self) -> tuple:
		"""What decides who reads and adds notes in this category."""
		return (cint(self.is_private), role_set(self.view_roles), role_set(self.create_roles))

	def refuse_unless_every_church(self):
		"""Only a user who reaches every church decides who reads a category, since every church files notes in it.

		Otherwise one branch's manager could untick Private and open every church's private notes to its staff.
		"""
		if self.flags.ignore_permissions or has_every_church(frappe.session.user):
			return
		frappe.throw(
			_(
				"Note categories are shared by every church. Only someone who works across every church "
				"can add or remove one, or change who reads and adds its notes."
			),
			frappe.PermissionError,
		)

	def can_read(self, user: str, author: str) -> bool:
		"""Whether *user* may read a note in this category written by *author*."""
		if self.is_private:
			return user == author
		return has_listed_role(user, self.view_roles)

	def can_add(self, user: str) -> bool:
		"""Whether *user* may add a note in this category."""
		return has_listed_role(user, self.create_roles)


def has_listed_role(user: str, rows: list) -> bool:
	"""Whether *user* holds one of the roles in *rows*; an empty list admits everyone."""
	roles = role_set(rows)
	return not roles or bool(roles.intersection(frappe.get_roles(user)))


def role_set(rows: list) -> frozenset[str]:
	return frozenset(row.role for row in rows)


def create_note_categories(names: tuple[str, ...] | None = None) -> None:
	"""Make the missing shipped categories, or only those in *names*, so a patch does not bring back a deleted one.

	Everyone reads General; only the care team and managers read Pastoral Care and Benevolence.
	"""
	pastoral_roles = [{"role": role} for role in PASTORAL_ROLES]
	categories = (
		{"category_name": GENERAL, "description": "Notes everyone on staff can read and add."},
		{
			"category_name": PASTORAL_CARE,
			"description": "Care and counseling notes. Only the care team and Church Managers can read them.",
			"view_roles": pastoral_roles,
			"create_roles": pastoral_roles,
		},
		{
			"category_name": BENEVOLENCE,
			"description": "Benevolence and alms case notes. Only the care team and Church Managers can read them.",
			"view_roles": pastoral_roles,
			"create_roles": pastoral_roles,
		},
	)
	for category in categories:
		if names is not None and category["category_name"] not in names:
			continue
		if not frappe.db.exists("Note Category", category["category_name"]):
			frappe.get_doc({"doctype": "Note Category", **category}).insert(ignore_permissions=True)
