# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Date each Communication Consent recorded in the future when it was entered.

The newest record decides, so one dated ahead outranked every later answer. Recorded On is
now refused when it is in the future, and this clears the ones saved before that.
"""

import frappe
from frappe.utils import now_datetime


def execute():
	Consent = frappe.qb.DocType("Communication Consent")
	(
		frappe.qb.update(Consent)
		.set(Consent.recorded_on, Consent.creation)
		.where(Consent.recorded_on > now_datetime())
		.run()
	)
