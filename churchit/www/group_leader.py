# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils import today

from churchit.church_communications.sending import can_send_texts
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_people.group_api import get_open_join_requests
from churchit.church_people.group_leaders import get_led_groups
from churchit.church_people.group_meetings import get_group_meetings, get_meets, get_roster
from churchit.church_scope import session_person
from churchit.www.directory import get_primary_emails, get_primary_phones

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/group-leader"
		raise frappe.Redirect

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = _("Lead a Group")
	context.person = session_person()
	groups = get_led_groups(context.person) if context.person else []
	# A reminder email links to one group.
	if frappe.form_dict.group in groups:
		groups = [frappe.form_dict.group]

	# church-scope: the groups the session user leads
	context.group_names = dict(
		frappe.get_all("Group", filters={"name": ("in", groups)}, fields=["name", "group_name"], as_list=True)
	)
	context.groups = sorted(groups, key=lambda group: context.group_names[group])
	context.rosters = {group: get_contact_roster(group) for group in groups}
	context.meetings = {group: get_group_meetings(group) for group in groups}
	context.upcoming = {group: get_upcoming(group) for group in groups if not context.meetings[group]}
	context.join_requests = get_open_join_requests(groups)
	# The message form shows only the ways the site can send, the checks message_group makes.
	context.can_send_email = can_send_email()
	context.can_send_texts = can_send_texts()


def get_upcoming(group: str) -> frappe._dict:
	"""The date of *group*'s next meeting after today, and whether a schedule of the group still runs."""
	# church-scope: the meetings of one group, which the session user leads
	next_date = frappe.db.get_value(
		"Function",
		{"group": group, "auto_repeat": 0, "start_date": (">", today())},
		"start_date",
		order_by="start_date asc",
	)
	return frappe._dict(next_date=next_date, has_schedule=bool(get_meets(group)))


def get_contact_roster(group: str) -> list[frappe._dict]:
	"""*group*'s living members, with the primary email and phone of each who shares them."""
	roster = get_roster(group)
	emails = get_primary_emails([person.name for person in roster if person.share_email])
	phones = get_primary_phones([person.name for person in roster if person.share_phone])
	for person in roster:
		person.email = emails.get(person.name)
		person.phone = phones.get(person.name)
	return roster
