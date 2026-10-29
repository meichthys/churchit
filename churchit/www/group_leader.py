# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_communications.sending import can_send_texts
from churchit.church_people.group_api import get_open_join_requests
from churchit.church_people.group_leaders import get_led_groups
from churchit.church_people.group_meetings import get_group_meetings, get_roster
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
	context.join_requests = get_open_join_requests(groups)
	context.can_send_texts = can_send_texts()


def get_contact_roster(group: str) -> list[frappe._dict]:
	"""*group*'s living members, with the primary email and phone of each who shares them."""
	roster = get_roster(group)
	emails = get_primary_emails([person.name for person in roster if person.share_email])
	phones = get_primary_phones([person.name for person in roster if person.share_phone])
	for person in roster:
		person.email = emails.get(person.name)
		person.phone = phones.get(person.name)
	return roster
