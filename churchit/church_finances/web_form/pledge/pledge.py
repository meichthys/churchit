# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

from churchit.church_finances.doctype.pledge.pledge import get_open_campaigns
from churchit.church_scope import session_person


def get_context(context):
	"""Offer only the open campaigns of the member's church, in place of the options Frappe found."""
	campaigns = get_open_campaigns()
	context.has_open_campaigns = bool(campaigns)
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "campaign":
			field.options = json.dumps([{"value": name, "label": title} for name, title in campaigns.items()])


def get_list_context(context):
	"""List only the login's own pledges, not every pledge that staff may read."""
	context.filters = {"person": session_person()}
	return context
