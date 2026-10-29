# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from churchit.church_people.group_meetings import get_meets
from churchit.church_people.group_requirements import check_member_requirements


class Group(Document):
	def onload(self):
		self.meets = get_meets(self.name)

	def validate(self):
		self.meets = get_meets(self.name)
		check_member_requirements(self)

	@property
	def member_count(self) -> int:
		return len(self.members)

	@property
	def is_full(self) -> bool:
		return bool(self.capacity) and self.member_count >= self.capacity

	@property
	def is_enrollment_open(self) -> bool:
		"""Whether a person can join, or ask to join, from the portal today."""
		closed = self.close_enrollment_on and getdate(self.close_enrollment_on) < getdate()
		return bool(
			self.status == "Active"
			and self.public
			and self.show_in_portal
			and not self.is_full
			and not closed
		)

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
		return bool(frappe.db.exists("Group Member", {"parent": self.name, "person": person}))


@frappe.whitelist(methods=["POST"])
def add_people(group: str, people: str | list[str], group_role: str | None = None):
	"""Add *people* to a Group, skipping anyone already in it."""
	doc = frappe.get_doc("Group", group)
	doc.check_permission("write")
	people = list(dict.fromkeys(frappe.parse_json(people)))
	existing = {member.person for member in doc.members}
	added = [person for person in people if person not in existing]
	for person in added:
		# `person` is a plain Link, which user permissions never measure against its church.
		frappe.has_permission("Person", doc=person, throw=True)
		doc.append("members", {"person": person, "group_role": group_role})
	if added:
		doc.save()
	return {"added": len(added), "already_members": len(people) - len(added)}
