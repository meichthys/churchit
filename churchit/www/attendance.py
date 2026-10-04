# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_ministries.member_attendance import CHECKED_IN, get_member_choices, get_own_attendance
from churchit.church_scope import session_person

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/attendance"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = "Attendance"
	context.person = session_person()
	context.attendance = get_own_attendance(context.person) if context.person else []
	context.choices = get_member_choices()
	for row in context.attendance:
		row.is_changeable = bool(context.choices) and row.attendance_type != CHECKED_IN
