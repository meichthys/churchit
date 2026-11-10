# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Add Connection Card and Connection Card Photo to Only for Local or Zero Retention Models on existing
sites, because a family card holds children's names. Only these two rows are added, each when it is
missing, and a list that an admin emptied stays empty. The rows of doctypes that are gone fail the
save, so the patch deletes them first, as fill_private_model_doctypes does."""

import frappe

from churchit.ai.flow_switch import forget_missing_blocked_doctypes
from churchit.ai.switch import SETTINGS

CARD_DOCTYPES = ("Connection Card", "Connection Card Photo")


def execute():
	forget_missing_blocked_doctypes()
	settings = frappe.get_single(SETTINGS)
	missing = [doctype for doctype in CARD_DOCTYPES if doctype not in settings.private_doctypes]
	if not (settings.private_model_doctypes and missing):
		return
	for doctype in missing:
		settings.append("private_model_doctypes", {"document_type": doctype})
	settings.save()
