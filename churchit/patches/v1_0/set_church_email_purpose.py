# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each existing Church Email the purpose and channel it was sent with: Church News, by email.

Runs after add_communication_purposes, which makes Church News. Safe to run again.
"""

import frappe

from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS


def execute():
	ChurchEmail = frappe.qb.DocType("Church Email")
	for column, value in ((ChurchEmail.purpose, CHURCH_NEWS), (ChurchEmail.channel, "Email")):
		frappe.qb.update(ChurchEmail).set(column, value).where(column.isnull() | (column == "")).run()
