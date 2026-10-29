# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Turn each existing Email Unsubscribe into Communication Consent, so consent agrees with today's opt-outs.

A global unsubscribe withdraws Email for every purpose; a church's unsubscribe withdraws its
people's Church News. Runs after add_communication_purposes, which makes Church News.
"""

import frappe

from churchit.church_communications.consent import record_unsubscribe
from churchit.church_communications.newsletter import UNSUBSCRIBE_REFERENCE


def execute():
	unsubscribes = frappe.get_all(
		"Email Unsubscribe",
		or_filters={"global_unsubscribe": 1, "reference_doctype": UNSUBSCRIBE_REFERENCE},
		fields=["email", "global_unsubscribe", "reference_doctype", "reference_name", "creation"],
		order_by="creation asc",
	)
	for unsubscribe in unsubscribes:
		record_unsubscribe(unsubscribe)
