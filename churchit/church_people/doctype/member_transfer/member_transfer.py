# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

from churchit.church_people.doctype.inactive_reason.inactive_reason import TRANSFERRED
from churchit.church_people.membership import ACTIVE, CONTACT, INACTIVE, MEMBER
from churchit.church_scope import CHURCH_FIELD, allowed_churches


class MemberTransfer(Document):
	def validate(self):
		self.validate_both_churches_are_mine()
		if self.is_confirming_move() and self.to_church == frappe.db.get_value(
			"Person", self.person, "church"
		):
			frappe.throw(_("{0} already belongs to {1}.").format(self.person, self.to_church))

	def validate_both_churches_are_mine(self):
		"""A transfer moves a person between churches the user holds, and no further.

		Nothing else stops it. `person` is a plain Link, and Frappe applies user
		permissions to Church rather than to Person, so it never looks at whose
		member this is; `to_church` is marked ignore_user_permissions; and
		`move_person` writes with ignore_permissions. Through the API that added
		up to any manager being able to take any member of any church.
		"""
		allowed = allowed_churches()
		if allowed is None:
			return

		for church in (frappe.db.get_value("Person", self.person, CHURCH_FIELD), self.to_church):
			if church and church not in allowed:
				frappe.throw(
					_("{0} is not one of your churches.").format(
						frappe.db.get_value("Church", church, "church_name") or church
					),
					frappe.PermissionError,
				)

	def on_update(self):
		if self.is_confirming_move():
			self.move_person()
		elif self.is_confirming_departure():
			self.mark_person_departed()
		elif self.is_confirming_arrival():
			self.mark_person_received()

	@property
	def is_confirming(self):
		return self.status == "Confirmed" and self.has_value_changed("status")

	def is_confirming_move(self):
		return bool(self.to_church) and self.is_confirming

	def is_confirming_departure(self):
		return self.direction == "Out" and not self.to_church and self.is_confirming

	def is_confirming_arrival(self):
		return self.direction == "In" and not self.to_church and self.is_confirming

	def mark_person_departed(self):
		"""A person who transfers out to another church is no longer a member here.

		The reason is one Inactive Reason for every transfer; this record keeps the other church.
		"""
		person = frappe.get_doc("Person", self.person)
		person.membership = CONTACT
		person.membership_status = INACTIVE
		person.inactive_reason = TRANSFERRED
		person.save(ignore_permissions=True)

	def mark_person_received(self):
		"""A person who transfers in becomes an active member here, with a Membership life event."""
		person = frappe.get_doc("Person", self.person)
		if person.membership == MEMBER and person.membership_status == ACTIVE:
			return
		notes = _("Transferred from {0}").format(self.other_church) if self.other_church else None
		person.append("life_events", {"event_type": "Membership", "date": nowdate(), "notes": notes})
		person.membership_status = ACTIVE
		person.save(ignore_permissions=True)

	def move_person(self):
		"""Move the person to the destination branch; their user permission follows."""
		person = frappe.get_doc("Person", self.person)
		person.church = self.to_church
		person.save(ignore_permissions=True)
