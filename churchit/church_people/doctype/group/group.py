# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from churchit.church_people.derived import warn_if_after_death
from churchit.church_people.group_meetings import get_meets
from churchit.church_people.group_requirements import check_member_requirements
from churchit.church_people.repeated_rows import refuse_repeated_people
from churchit.unique_names import refuse_a_second_with_this_name


class Group(Document):
	def onload(self):
		self.meets = get_meets(self.name)

	def validate(self):
		self.meets = get_meets(self.name)
		refuse_a_second_with_this_name(
			self, "group_name", _("There is already a group called {0}. Give this group another name.")
		)
		refuse_repeated_people(self, "members", "person")
		check_member_requirements(self)
		self.warn_about_members_after_death()

	def warn_about_members_after_death(self):
		"""Warn about each person added to the members after their recorded death. A member row has no date."""
		before = self.get_doc_before_save()
		people_before = {row.person for row in before.members} if before else set()
		for row in self.members:
			if row.person not in people_before:
				warn_if_after_death(row.person, getdate(), _("group membership"))

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


@frappe.whitelist(methods=["POST"])
def add_people(group: str, people: str | list[str], group_role: str | None = None) -> dict:
	"""Add *people* to a Group, skipping anyone already in it, and count both. Changes data."""
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
