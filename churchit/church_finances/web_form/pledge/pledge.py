# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe import _

from churchit.church_finances.doctype.pledge.pledge import get_open_campaigns, get_pledges_by_campaign
from churchit.church_people.member_access import hide_edit_unless_writable
from churchit.church_scope import session_person


def get_context(context):
	"""Offer only the open campaigns of the member's church, in place of the options Frappe found.

	A pledge that staff recorded for the member opens without an Edit button. A pledge that is open shows its
	campaign title, and the form reminds the member of a pledge to the campaign they pick.
	"""
	hide_edit_unless_writable(context, "Pledge")
	campaigns = get_open_campaigns()
	context.has_open_campaigns = bool(campaigns)
	context.existing_pledges = get_pledges_by_campaign()
	context.edit_pledge_label = _("Edit that pledge?")
	if context.get("reference_doc"):
		context.link_titles = {
			"campaign": frappe.db.get_value("Pledge Campaign", context.reference_doc.campaign, "title")
		}
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "campaign":
			field.options = json.dumps([{"value": name, "label": title} for name, title in campaigns.items()])


def get_list_context(context):
	"""List only the login's own pledges, not every pledge that staff may read."""
	context.filters = {"person": session_person()}
	return context
