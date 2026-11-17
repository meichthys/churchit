# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Print times without seconds and amounts with the currency in three notifications that sites keep.

Room Booking Decided, Church Task Due and New Alms Request are inserted records, not shipped files, so
each pair below replaces one piece of text this app inserted. A piece the church rewrote stays.
"""

import frappe

from churchit.church_finances.doctype.alms_request.alms_request import ALMS_NOTIFICATION
from churchit.church_operations.doctype.church_task.church_task import DUE_NOTIFICATION
from churchit.church_operations.doctype.room_booking.room_booking import DECIDED_NOTIFICATION

FIXES = {
	DECIDED_NOTIFICATION: (
		(
			"{{ frappe.utils.format_datetime(doc.start_datetime) }}",
			'{{ frappe.utils.format_datetime(doc.start_datetime, "EEEE, MMMM d, yyyy h:mm a") }}',
		),
		(
			"{{ frappe.utils.format_datetime(doc.end_datetime) }}",
			'{{ frappe.utils.format_datetime(doc.end_datetime, "EEEE, MMMM d, yyyy h:mm a") }}',
		),
	),
	DUE_NOTIFICATION: (
		(
			"{{ frappe.utils.format_datetime(doc.due_date) }}",
			'{{ frappe.utils.format_datetime(doc.due_date, "EEEE, MMMM d, yyyy h:mm a") }}',
		),
	),
	ALMS_NOTIFICATION: (
		(
			"{{ frappe.utils.fmt_money(doc.amount) }}",
			'{{ frappe.utils.fmt_money(doc.amount, currency=frappe.db.get_default("currency")) }}',
		),
	),
}


def execute():
	for name, pairs in FIXES.items():
		message = frappe.db.get_value("Notification", name, "message")
		if not message:
			continue
		fixed = message
		for shipped, new in pairs:
			fixed = fixed.replace(shipped, new)
		if fixed != message:
			frappe.db.set_value("Notification", name, "message", fixed)
