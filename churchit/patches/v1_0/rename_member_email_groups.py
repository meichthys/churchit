# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rename each church's member Email Group off its abbreviation onto its name.

Two churches may share an abbreviation, and an Email Group is keyed by its
title, so the old name could merge two congregations' recipient lists. Renaming
rather than recreating keeps everyone who unsubscribed unsubscribed.
"""

import frappe

from churchit.church_communications.newsletter import MEMBER_EMAIL_GROUP, member_email_group
from churchit.church_scope import is_multi_church


def execute():
	if not is_multi_church():
		return

	for church in frappe.get_all("Church", fields=["name", "abbreviation"]):
		old_title = f"{MEMBER_EMAIL_GROUP} - {church.abbreviation}"
		new_title = member_email_group(church.name)
		if old_title == new_title or not frappe.db.exists("Email Group", old_title):
			continue
		if frappe.db.exists("Email Group", new_title):
			# Two churches shared the abbreviation and one has already claimed the
			# new name; leave the merged group for the church to sort out by hand.
			continue
		frappe.rename_doc("Email Group", old_title, new_title, force=True, show_alert=False)
