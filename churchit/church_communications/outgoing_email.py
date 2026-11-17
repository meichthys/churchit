# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Notifications on a site that has no Email Account to send from.

Frappe gap: frappe.sendmail throws "Please setup default outgoing Email Account" when no account can
send. A Notification adds a "sent" email to the record's timeline first, then catches the error,
skips its bell entry and leaves the message for the person who saved the record, who cannot act on
it. A Notification Log made in the request (not in Frappe's background job) leaves the same message
from its own email. Upstream, frappe.sendmail could log and skip instead of frappe.throw.
"""

import frappe
from frappe import _
from frappe.email.doctype.notification.notification import get_reference_doctype
from frappe.utils.html_utils import clean_html

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)

# Frappe's own words in EmailAccount.find_outgoing.
NO_ACCOUNT = "Please setup default outgoing Email Account from Tools > Email Account"


class EmailOnlyWithAnAccount:
	"""extend_doctype_class on Notification: with no account, send no email, so the record gets no
	false "sent" entry and the saver no message, and the bell entry still follows."""

	def send_an_email(self, doc, context, template_content=None):
		# Frappe sends from sender_email only when the notification also names a sender.
		sender = self.sender_email if self.sender else None
		if can_send_email(sender, get_reference_doctype(doc)):
			super().send_an_email(doc, context, template_content)


def forget_no_account_message(doc, method=None):
	"""after_insert on Notification Log: remove Frappe's message about the missing account.

	Frappe catches the error of the bell entry's email but keeps its message. Removes only that
	message, and only while no account can send.
	"""
	if can_send_email():
		return
	message = _(NO_ACCOUNT)
	# A tuple, because a message shown as a list or table is a list, which a set cannot hold.
	shown = (message, clean_html(message))
	frappe.local.message_log = [
		entry for entry in frappe.local.message_log if entry.get("message") not in shown
	]
