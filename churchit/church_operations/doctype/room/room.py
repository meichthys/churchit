# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from frappe.utils.user import get_users_with_role

from churchit.church_operations.doctype.room_booking.room_booking import (
	APPROVER_ROLES,
	LISTED_APPROVER_ROLES,
)
from churchit.church_scope import (
	church_filters,
	default_church,
	has_church_access,
	refuse_another_churches_record,
)


class Room(Document):
	def validate(self):
		self.refuse_approvers_who_cannot_approve()
		self.refuse_a_second_room_with_this_name()
		self.refuse_setups_with_one_name()
		self.refuse_another_churches_question_set()

	def refuse_approvers_who_cannot_approve(self):
		for row in self.approvers:
			roles = set(frappe.get_roles(row.user))
			if not roles & LISTED_APPROVER_ROLES or not has_church_access(row.user, self.room_church):
				frappe.throw(
					_(
						"{0} cannot approve bookings of this room. An approver needs the Church Staff or "
						"Church Manager role and access to the church of the room."
					).format(row.user)
				)

	def get_approvers(self) -> list[str]:
		"""The listed approvers, or the Church Managers when none are listed, who may still approve."""
		users = [row.user for row in self.approvers] or get_users_with_role("Church Manager")
		return [user for user in users if self.is_approver(user)]

	def is_approver(self, user: str) -> bool:
		"""A listed user who still holds a staff role, or with no list, a Church Manager, of the room's church."""
		if not has_church_access(user, self.church or self.shared_by_church):
			return False
		roles = set(frappe.get_roles(user))
		if self.approvers:
			return user in {row.user for row in self.approvers} and bool(LISTED_APPROVER_ROLES & roles)
		return bool(APPROVER_ROLES & roles)

	@property
	def room_church(self) -> str | None:
		"""The church of the room. For a new room, the one ensure_church gives it after the controller runs."""
		return self.church or self.shared_by_church or default_church()

	def refuse_a_second_room_with_this_name(self):
		"""Refuse a room name that a room of this church, or a shared room, already has.

		Every church lists a shared room, so a shared room's name is compared with every room.
		"""
		filters = {"room_name": self.room_name, "name": ("!=", self.name or "")}
		if not cint(self.is_shared):
			filters = church_filters(self.room_church, **filters)
		# church-scope: a name must not repeat among the rooms one church lists, whoever owns them
		if frappe.db.exists("Room", filters):
			frappe.throw(
				_("There is already a room called {0}. Give this room another name.").format(
					frappe.bold(self.room_name)
				)
			)

	def refuse_setups_with_one_name(self):
		names = [row.setup_name for row in self.setups]
		repeated = sorted({name for name in names if names.count(name) > 1})
		if repeated:
			frappe.throw(_("Give each setup its own name: {0}.").format(", ".join(repeated)))

	def refuse_another_churches_question_set(self):
		"""The booking questions come from a Question Set of this church or a shared one."""
		# Only when they change, as on Function: a save of the room for another reason must not trip it.
		if any(self.has_value_changed(field) for field in ("question_set", "church", "is_shared")):
			refuse_another_churches_record(self, "Question Set", self.question_set)
