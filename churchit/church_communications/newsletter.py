# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import contextlib

import frappe
from frappe import _
from frappe.utils import cint

from churchit.church_scope import is_multi_church, session_church, session_person
from churchit.contacts import get_primary_email, get_primary_emails

MEMBER_EMAIL_GROUP = "Church Members"


def member_email_group(church=None):
	"""The Email Group a church's members belong to: one per church once branches exist.

	Named after the church rather than its abbreviation, which is a free-form
	label two churches may share: an Email Group is keyed by its title, so a
	repeated abbreviation silently merged two congregations' recipient lists.
	"""
	if not is_multi_church() or not church:
		return MEMBER_EMAIL_GROUP
	return f"{MEMBER_EMAIL_GROUP} - {frappe.db.get_value('Church', church, 'church_name')}"


@frappe.whitelist()
def sync_member_email_group():
	"""Pull email addresses from Person records into the church newsletter
	Email Group so the recipient list never has to be maintained by hand.

	Each Person contributes the one address marked primary in their Emails
	table, since a member's work address is not newsletter material unless they
	made it their primary. Re-running only adds addresses that are not already in
	the group, so anyone who unsubscribed via a newsletter link stays unsubscribed.
	In multi-church mode each church has its own group, created on first sync.
	"""
	if not is_multi_church():
		# church-scope: one church on the site, so its one group holds everyone
		if frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
			add_members(MEMBER_EMAIL_GROUP, frappe.get_all("Person", pluck="name"))
		return

	for church in frappe.get_all("Church", pluck="name"):
		# church-scope: scheduled daily job building one group per church, filtered to
		# the church whose group it is. Not church_filters: a shared Person cannot
		# exist, and admitting the empty church would put strangers in every group.
		people = frappe.get_all("Person", filters={"church": church}, pluck="name")
		if people:
			add_members(ensure_email_group(member_email_group(church)), people)


def add_members(group, people):
	"""Add the primary email of each person to the group, skipping addresses already in it."""
	emails = set(get_primary_emails("Person", people).values())
	if not emails:
		return

	existing = set(
		frappe.get_all(
			"Email Group Member",
			filters={"email_group": group, "email": ("in", list(emails))},
			pluck="email",
		)
	)

	for email in sorted(emails - existing):
		with contextlib.suppress(frappe.UniqueValidationError, frappe.InvalidEmailAddressError):
			frappe.get_doc({"doctype": "Email Group Member", "email_group": group, "email": email}).insert(
				ignore_permissions=True
			)


def ensure_email_group(title):
	if not frappe.db.exists("Email Group", title):
		frappe.get_doc({"doctype": "Email Group", "title": title}).insert(ignore_permissions=True)
	return title


def _current_subscriber_email():
	"""Return the email address to manage for the logged-in user.

	Prefers the linked Person's primary email, falling back to the User's own
	email. Returns ``None`` for guests or users with no email on file.
	"""
	user = frappe.session.user
	if user == "Guest":
		return None
	person = session_person()
	email = get_primary_email("Person", person) if person else None
	return email or frappe.db.get_value("User", user, "email")


@frappe.whitelist()
def get_subscription_status():
	"""Return the logged-in member's church-newsletter subscription status."""
	email = _current_subscriber_email()
	group = member_email_group(session_church())
	subscribed = False
	if email and frappe.db.exists("Email Group", group):
		member = frappe.db.get_value(
			"Email Group Member",
			{"email_group": group, "email": email},
			["unsubscribed"],
			as_dict=True,
		)
		subscribed = bool(member) and not member.unsubscribed
	return {"email": email, "subscribed": subscribed, "newsletter": group}


@frappe.whitelist()
def set_subscription(subscribed: bool):
	"""Subscribe or unsubscribe the logged-in member to the church newsletter.

	Backed by the Email Group Member ``unsubscribed`` flag rather than deleting
	the row, so the daily Person sync never silently re-subscribes someone who
	opted out.
	"""
	email = _current_subscriber_email()
	if not email:
		frappe.throw(_("No email address is on file for your account. Please contact the church office."))

	subscribe = bool(cint(subscribed))
	group = ensure_email_group(member_email_group(session_church()))

	name = frappe.db.get_value("Email Group Member", {"email_group": group, "email": email}, "name")
	if name:
		frappe.db.set_value("Email Group Member", name, "unsubscribed", 0 if subscribe else 1)
	else:
		frappe.get_doc(
			{
				"doctype": "Email Group Member",
				"email_group": group,
				"email": email,
				"unsubscribed": 0 if subscribe else 1,
			}
		).insert(ignore_permissions=True)
	return {"subscribed": subscribe}
