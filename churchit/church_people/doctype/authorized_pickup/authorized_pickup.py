# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from churchit.church_people import household
from churchit.church_scope import refuse_another_churches_parent


class AuthorizedPickup(Document):
	def validate(self):
		refuse_another_churches_parent(
			self,
			"family",
			_("{0} belongs to another church, so only that church can say who may collect its children."),
		)
		self.refuse_the_household()
		if frappe.db.exists(
			"Authorized Pickup", {"family": self.family, "person": self.person, "name": ("!=", self.name)}
		):
			frappe.throw(_("{0} may already collect this family's children.").format(self.bold_name))

	def refuse_the_household(self):
		"""Refuse an Adult or a Child of the family's household."""
		refusals = {
			household.ADULT: _("{0} is an Adult of this household and may always collect its children."),
			household.CHILD: _("{0} is a child of this family."),
		}
		role = frappe.db.get_value(
			"Family Members",
			{"parenttype": "Family", "parent": self.family, "member": self.person},
			"household_role",
		)
		if role in refusals:
			frappe.throw(refusals[role].format(self.bold_name))

	@property
	def bold_name(self) -> str:
		return frappe.bold(escape_html(self.person_name or self.person))


def set_pickups_church(family: str, church: str | None) -> None:
	"""Move *family*'s authorized pickups to the church the family moved to, so that church manages them."""
	frappe.db.set_value("Authorized Pickup", {"family": family}, "church", church, update_modified=False)
