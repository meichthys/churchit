# Copyright (c) 2025, meichthys and contributors
# For license information, please see license.txt

import frappe

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
