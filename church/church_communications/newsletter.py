# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

MEMBER_EMAIL_GROUP = "Church Members"


@frappe.whitelist()
def sync_member_email_group():
	"""Pull email addresses from Person records into the church newsletter
	Email Group so the recipient list never has to be maintained by hand.

	Uses Frappe's native ``Email Group.import_from()``, which reads the
	Email-type field on Person and inserts an Email Group Member per address.
	The unique index on (email_group, email) makes re-running idempotent, and
	anyone who unsubscribed via a newsletter link is left untouched on
	subsequent syncs.
	"""
	if not frappe.db.exists("Email Group", MEMBER_EMAIL_GROUP):
		return
	frappe.get_doc("Email Group", MEMBER_EMAIL_GROUP).import_from("Person")


def _current_subscriber_email():
	"""Return the email address to manage for the logged-in user.

	Prefers the linked Person's email, falling back to the User's own email.
	Returns ``None`` for guests or users with no email on file.
	"""
	user = frappe.session.user
	if user == "Guest":
		return None
	person = frappe.db.get_value("Person", {"user": user}, "name")
	email = frappe.db.get_value("Person", person, "email") if person else None
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
	frappe.db.commit()
	return {"subscribed": subscribe}
