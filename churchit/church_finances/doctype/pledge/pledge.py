# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from churchit.church_finances.doctype.fund.fund import format_amount
from churchit.church_finances.report.pledge_progress.pledge_progress import get_received_for_pledge
from churchit.church_people.derived import warn_if_after_death
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import (
	church_filters,
	refuse_another_churches_parent,
	session_church,
	session_person,
)


class Pledge(Document):
	def validate(self):
		if not self.amount or self.amount < 0:
			frappe.throw(_("Enter the amount you pledge."))

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

		if self.has_value_changed("person"):
			warn_if_after_death(self.person, today(), _("pledge"))

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


@frappe.whitelist(methods=["GET"])
def get_given_so_far(pledge: str) -> str:
	"""A sentence that says how much was given toward *pledge* so far. Reads only."""
	doc = frappe.get_doc("Pledge", pledge)
	doc.check_permission("read")

	return _("Given so far: {0} of {1}.").format(
		format_amount(get_received_for_pledge(doc)), format_amount(doc.amount)
	)


def get_pledges_by_campaign() -> dict[str, dict]:
	"""{campaign: {"name", "message"}} of the signed-in member's own pledges, for the form's reminder."""
	person = session_person()
	if not person:
		return {}

	# church-scope: the member's own pledges
	rows = frappe.get_all(
		"Pledge", filters={"person": person}, fields=["name", "campaign", "amount"], order_by="creation"
	)
	titles = dict(
		frappe.get_all(
			"Pledge Campaign",
			filters={"name": ("in", [row.campaign for row in rows])},
			fields=["name", "title"],
			as_list=True,
		)
	)
	return {
		row.campaign: {
			"name": row.name,
			"message": _("You pledged {0} to {1}.").format(
				format_amount(row.amount), titles.get(row.campaign) or row.campaign
			),
		}
		for row in rows
	}
