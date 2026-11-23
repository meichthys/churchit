# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Live updates for open website pages: a hint to Frappe's website room when a record they show changes.

The hint names only the doctype that changed, never a record: every visitor's page is in the website
room, guests included. A page lists the doctypes it shows on its live regions (data-live) and reads
itself again (public/js/website_live.js), so each visitor gets what their own request allows. A
record counts when it is on the website before or after the change, so a page also drops a record
that stops being published.
"""

import frappe
from frappe.realtime import get_website_room

EVENT = "churchit_website"


def notify_change(doc, method: str | None = None) -> None:
	"""doc_events hook: hint open pages when *doc* is, or was, shown on the website.

	A save of a Function's attendance (attendance.save_attendance) changes nothing a page shows, and
	each check-in and sign-up makes one, so it sends no hint."""
	if doc.flags.attendance_only:
		return
	before = doc.get_doc_before_save() if method == "on_update" else None
	if is_shown(doc) or (before and is_shown(before)):
		notify(doc.doctype)


def is_shown(doc) -> bool:
	"""Whether the public website shows *doc*, by the fields its pages filter on."""
	if doc.doctype == "Bulletin":
		return bool(doc.get("publish") and doc.get("share_announcements"))
	return bool(doc.get("publish"))


def notify(doctype: str) -> None:
	"""Tell every open website page that a *doctype* record changed, once the transaction commits."""
	if frappe.flags.in_import or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	frappe.publish_realtime(EVENT, {"doctype": doctype}, room=get_website_room(), after_commit=True)
