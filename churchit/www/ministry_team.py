# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.doctype.function.function import get_team_schedule
from churchit.church_ministries.member_ministry_team import (
	get_calendar_links,
	get_own_assignments,
	get_own_blocks,
	get_own_positions,
)
from churchit.church_scope import session_person

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/ministry-team"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = "Ministry Team"
	context.person = session_person()
	context.assignments = get_own_assignments(context.person) if context.person else []
	context.blocks = get_own_blocks(context.person) if context.person else []
	context.positions = get_own_positions(context.person) if context.person else []
	context.calendar = get_calendar_links(context.person) if context.person else None
	context.schedules = {
		function: get_team_schedule(frappe.get_doc("Function", function), context.person)
		for function in {row.function for row in context.assignments}
	}
