# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add Contact Verification to Blocked from Flow Knowledge on existing sites, because its rows hold notes
about people and the photos of their returned cards. Only this row is added, when it is missing, and a
list that an admin emptied stays empty. The rows of doctypes that are gone fail the save, so the patch
deletes them first."""

import frappe

from churchit.ai.flow_switch import forget_missing_blocked_doctypes
from churchit.ai.switch import SETTINGS

VERIFICATION = "Contact Verification"


def execute():
	forget_missing_blocked_doctypes()
	settings = frappe.get_single(SETTINGS)
	if settings.blocked_knowledge_doctypes and VERIFICATION not in settings.blocked_doctypes:
		settings.append("blocked_knowledge_doctypes", {"document_type": VERIFICATION})
		settings.save()
