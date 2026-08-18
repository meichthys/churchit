# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import contextlib

import frappe
from frappe import _
from frappe.utils import cint

from churchit.contacts import get_primary_email, get_primary_emails

MEMBER_EMAIL_GROUP = "Church Members"


@frappe.whitelist()
def sync_member_email_group():
	"""Pull email addresses from Person records into the church newsletter
	Email Group so the recipient list never has to be maintained by hand.

	Each Person contributes the one address marked primary in their Emails
	table, since a member's work address is not newsletter material unless they
	made it their primary. Re-running only adds addresses that are not already in
	the group, so anyone who unsubscribed via a newsletter link stays unsubscribed.
	"""
	if not frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
		return

	people = frappe.get_all("Person", pluck="name")
	emails = set(get_primary_emails("Person", people).values())
	if not emails:
		return

	existing = set(
		frappe.get_all(
			"Email Group Member",
			filters={"email_group": MEMBER_EMAIL_GROUP, "email": ("in", list(emails))},
			pluck="email",
		)
	)

	for email in sorted(emails - existing):
		with contextlib.suppress(frappe.UniqueValidationError, frappe.InvalidEmailAddressError):
			frappe.get_doc(
				{
					"doctype": "Email Group Member",
					"email_group": MEMBER_EMAIL_GROUP,
					"email": email,
				}
			).insert(ignore_permissions=True)


def _current_subscriber_email():
	"""Return the email address to manage for the logged-in user.

	Prefers the linked Person's primary email, falling back to the User's own
	email. Returns ``None`` for guests or users with no email on file.
	"""
	user = frappe.session.user
	if user == "Guest":
		return None
	person = frappe.db.get_value("Person", {"user": user}, "name")
	email = get_primary_email("Person", person) if person else None
	return email or frappe.db.get_value("User", user, "email")


@frappe.whitelist()
def get_subscription_status():
	"""Return the logged-in member's church-newsletter subscription status."""
	email = _current_subscriber_email()
	subscribed = False
	if email and frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
		member = frappe.db.get_value(
			"Email Group Member",
			{"email_group": MEMBER_EMAIL_GROUP, "email": email},
			["unsubscribed"],
			as_dict=True,
		)
		subscribed = bool(member) and not member.unsubscribed
	return {"email": email, "subscribed": subscribed, "newsletter": MEMBER_EMAIL_GROUP}


@frappe.whitelist()
def set_subscription(subscribed):
	"""Subscribe or unsubscribe the logged-in member to the church newsletter.

	Backed by the Email Group Member ``unsubscribed`` flag rather than deleting
	the row, so the daily Person sync never silently re-subscribes someone who
	opted out.
	"""
	email = _current_subscriber_email()
	if not email:
		frappe.throw(_("No email address is on file for your account. Please contact the church office."))

	subscribe = bool(cint(subscribed))

	if not frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
		frappe.get_doc({"doctype": "Email Group", "title": MEMBER_EMAIL_GROUP}).insert(ignore_permissions=True)

	name = frappe.db.get_value(
		"Email Group Member", {"email_group": MEMBER_EMAIL_GROUP, "email": email}, "name"
	)
	if name:
		frappe.db.set_value("Email Group Member", name, "unsubscribed", 0 if subscribe else 1)
	else:
		frappe.get_doc(
			{
				"doctype": "Email Group Member",
				"email_group": MEMBER_EMAIL_GROUP,
				"email": email,
				"unsubscribed": 0 if subscribe else 1,
			}
		).insert(ignore_permissions=True)
	return {"subscribed": subscribe}
