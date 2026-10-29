# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import (
	church_filters,
	refuse_another_churches_parent,
	session_church,
	session_person,
)


class Pledge(Document):
	def validate(self):
		if is_portal_member() or frappe.flags.in_web_form:
			self.take_members_own_pledge()
		else:
			# `person` and `family` are plain Links, which user permissions never measure against their church.
			frappe.has_permission("Person", doc=self.person, throw=True)
			if self.family:
				frappe.has_permission("Family", doc=self.family, throw=True)
			refuse_another_churches_parent(
				self,
				"campaign",
				_("{0} belongs to another church, so only that church can take pledges to it."),
			)

	def before_save(self):
		person_name = frappe.db.get_value("Person", self.person, "full_name")
		campaign_title = frappe.db.get_value("Pledge Campaign", self.campaign, "title")
		self.title = " - ".join(filter(None, (person_name, campaign_title)))

	def take_members_own_pledge(self):
		"""A member (or anyone on the web form) pledges only for themselves, to an open campaign of their church."""
		own_person = session_person()
		if not own_person:
			frappe.throw(_("No Person record is linked to your account."))
		# Staff can open any pledge of their church on the form; that must not move it to them.
		if not self.is_new() and self.get_doc_before_save().person != own_person:
			frappe.throw(_("You can change only your own pledges here."), frappe.PermissionError)
		self.person = own_person
		if self.campaign not in get_open_campaigns():
			frappe.throw(_("This campaign is not open for your pledges."), frappe.PermissionError)
		if self.family and self.family != frappe.db.get_value("Person", self.person, "family"):
			frappe.throw(_("You can pledge only for your own household."), frappe.PermissionError)


def get_open_campaigns() -> dict[str, str]:
	"""{name: title} of the campaigns the signed-in member may pledge to: their church's, not ended yet."""
	if not session_person():
		return {}
	return dict(
		frappe.get_all(
			"Pledge Campaign",
			filters=church_filters(session_church(), end_date=(">=", today())),
			fields=["name", "title"],
			order_by="end_date asc",
			as_list=True,
		)
	)
