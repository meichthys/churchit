# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.member_ministry_team import (
	can_pass_on,
	get_assignment_by_key,
	get_pending_replacement,
)

no_cache = 1


def get_context(context):
	"""Anyone holding a request email's link may answer it, signed in or not."""
	assignment = get_assignment_by_key(frappe.form_dict.get("key"))

	context.no_cache = 1
	context.title = "Ministry Team Request"
	context.key = assignment.response_key
	context.request = assignment.get_email_context()
	context.has_started = assignment.has_started
	context.can_pass_on = can_pass_on(assignment)
	context.pending_replacement = get_pending_replacement(assignment)
	context.replaced_by = assignment.replaced_by
