# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Contact page's form, in place of Frappe's: a message goes to the church whose page it came from.

Frappe's handler mails every message to Contact Us Settings' one Forward To Email and stores it with
no church. This one sends a message from a branch's page to the branch, keeps it as a Communication
on the Church, so staff find it on the Church's timeline, and names the church in its replies.
"""

from contextlib import suppress

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, validate_email_address

from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import root_church
from churchit.church_website.pages import get_switched_off_pages


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=60 * 60)
def send_message(email: str, message: str, subject: str = "General", website: str | None = None) -> str:
	"""Send a Contact page message to the church the page is about, and return the thanks. Sends messages.

	The church is the page's ``?church=`` selection (``selected_church_name``), so an unknown or
	unpublished church falls back to the main church. Only a bot fills in the hidden *website* field;
	it is thanked and nothing is sent.
	"""
	if (
		frappe.db.get_single_value("Contact Us Settings", "is_disabled")
		or "contact" in get_switched_off_pages()
	):
		frappe.throw(_("The Contact page is switched off."), frappe.PermissionError)

	church = frappe.get_cached_doc("Church", selected_church_name())
	thanks = _("Thank you. {0} has your message and will answer you by email.").format(church.church_name)
	if website:
		return thanks

	email = validate_email_address(email.strip(), throw=True)
	if not message.strip():
		frappe.throw(_("Write your message."))

	subject = _("Contact page: {0}").format(subject.strip()[:140] or _("General"))
	content = escape_html(message.strip()).replace("\n", "<br>")
	# The desk timeline prints a Communication's subject as HTML.
	add_communication(church, email, escape_html(subject), content)
	with suppress(frappe.OutgoingEmailError):
		if recipient := get_message_recipient(church):
			frappe.sendmail(recipients=recipient, reply_to=email, subject=subject, content=content)
		if frappe.db.get_single_value("Contact Us Settings", "send_acknowledgement_email"):
			frappe.sendmail(
				recipients=email,
				subject=_("{0} has your message").format(church.church_name),
				content=thanks,
			)
	# A failed send leaves its error message for the response; the visitor's message is kept anyway.
	frappe.clear_last_message()
	return thanks


def get_message_recipient(church: Document) -> str | None:
	"""Where a message to *church* goes: a branch's own email, else the main church's inbox.

	The main church's inbox is Contact Us Settings' Forward To Email, where every message went before
	this form, else the main church's email.
	"""
	root = root_church()
	if church.name != root and church.email:
		return church.email
	return frappe.db.get_single_value("Contact Us Settings", "forward_to_email") or frappe.db.get_value(
		"Church", root, "email"
	)


def add_communication(church: Document, sender: str, subject: str, content: str) -> None:
	"""Keep the message as an open, received Communication on *church*."""
	frappe.get_doc(
		{
			"doctype": "Communication",
			"communication_type": "Communication",
			"sent_or_received": "Received",
			"status": "Open",
			"sender": sender,
			"subject": subject,
			"content": content,
			"reference_doctype": "Church",
			"reference_name": church.name,
		}
	).insert(ignore_permissions=True)
