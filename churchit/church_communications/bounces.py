# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Email addresses whose mail came back.

Frappe has a Bounced delivery status but nothing sets it, so a bounce report that reaches
the church's inbox marks the address Email Bounced on every record holding it.

Frappe stores a received report as a Communication with the report's text and the headers
of the returned message, but drops its machine-readable part (Action, Status), so the text
decides. Frappe links a report to the sent Communication through `in_reply_to` only when the
report carries an In-Reply-To header, as Gmail and Microsoft 365 reports do and Postfix does not.

Anyone can send mail that looks like a report, so a report marks only addresses the site mailed lately.
"""

import re

import frappe
from frappe.query_builder import Criterion
from frappe.utils import EMAIL_STRING_PATTERN, add_days, extract_email_id, now_datetime, strip_html

from churchit.contacts import CONTACT_PARENTS, EMAIL_DOCTYPE

BOUNCE_SENDERS = ("mailer-daemon", "postmaster")
# Mail servers retry for up to 5 days before they report a failure, and Frappe keeps sent mail in
# Email Queue for 30 days unless Log Settings says otherwise.
RECENT_DAYS = 7
ADDRESS = EMAIL_STRING_PATTERN.pattern
# Where Postfix, Gmail and Microsoft 365 reports name an address that failed.
FAILED_RECIPIENTS = re.compile(
	rf"^[ \t]*<{ADDRESS}>:|wasn.t delivered to\s+{ADDRESS}|your message to\s+{ADDRESS}\s+couldn.t be delivered",
	re.IGNORECASE | re.MULTILINE,
)
# An enhanced status code (RFC 3463): 2.x.x delivered, 4.x.x delayed, 5.x.x failed.
STATUS_CODE = re.compile(r"(?<![\d.])[245]\.\d{1,3}\.\d{1,3}(?![\d.])")
# Failures that say nothing against the address: a policy block (5.7.x), often of the church's own
# server or its DMARC, and a full mailbox (5.2.2).
NOT_THE_ADDRESS = ("5.7.", "5.2.2")
# The words a report with no status code uses when delivery failed for good. A delay warning has none.
FAILED_WORDS = re.compile(
	r"could\s+not\s+be\s+delivered\s+to|couldn.t\s+be\s+delivered|wasn.t\s+delivered", re.IGNORECASE
)


def bounced_addresses(emails: list[str]) -> set[str]:
	"""The addresses among *emails* marked Email Bounced on any record, compared without case."""
	if not emails:
		return set()
	rows = frappe.get_all(
		EMAIL_DOCTYPE, filters={"email_address": ("in", emails), "is_bounced": 1}, pluck="email_address"
	)
	bounced = {row.lower() for row in rows}
	return {email for email in emails if email.lower() in bounced}


def record_bounce(doc, method=None):
	"""after_insert on Communication: mark the addresses a received bounce report names.

	A report counts when a mailer-daemon or postmaster address sent it and it says delivery
	failed for good, so a delay warning changes nothing. Each address it names as failed that
	the site mailed lately is marked on every record holding it, and the sent Communication it
	answers, when Frappe linked one, is marked Bounced. Nothing here raises on mail it cannot read.
	"""
	if not is_from_mail_system(doc):
		return
	text = doc.text_content or strip_html(doc.content or "")
	if not is_permanent_failure(text):
		return

	mark_bounced(get_recent_recipients(get_failed_addresses(text)))
	if doc.in_reply_to:
		frappe.db.set_value(
			"Communication",
			{"name": doc.in_reply_to, "sent_or_received": "Sent"},
			"delivery_status",
			"Bounced",
			update_modified=False,
		)


def is_from_mail_system(doc) -> bool:
	"""True for an email received from a mailer-daemon or postmaster address."""
	local_part = (doc.sender or "").partition("@")[0].lower()
	return (
		doc.sent_or_received == "Received"
		and doc.communication_medium == "Email"
		and local_part in BOUNCE_SENDERS
	)


def is_permanent_failure(text: str) -> bool:
	"""True when the report *text* says the address failed for good.

	Each status code it gives must be a 5.x.x that is not a policy block or a full mailbox.
	A report with no status code counts by its words.
	"""
	codes = STATUS_CODE.findall(text)
	if not codes:
		return bool(FAILED_WORDS.search(text))
	return all(code.startswith("5.") and not code.startswith(NOT_THE_ADDRESS) for code in codes)


def get_failed_addresses(text: str) -> set[str]:
	"""The addresses *text* names as failed, in lower case and without a full stop that ends a sentence."""
	return {
		address.lower().rstrip(".")
		for match in FAILED_RECIPIENTS.findall(text)
		for address in match
		if address
	}


def get_recent_recipients(emails: set[str]) -> set[str]:
	"""The addresses among *emails*, in lower case, that the site sent mail to in the last RECENT_DAYS days."""
	if not emails:
		return set()
	Recipient = frappe.qb.DocType("Email Queue Recipient")
	# Frappe keeps a recipient as the bare address or as "Name <address>".
	named = Criterion.any([Recipient.recipient.like(f"%<{email}>") for email in emails])
	sent = (
		frappe.qb.from_(Recipient)
		.select(Recipient.recipient)
		.where(Recipient.status == "Sent")
		.where(Recipient.creation >= add_days(now_datetime(), -RECENT_DAYS))
		.where(Recipient.recipient.isin(list(emails)) | named)
		.run(pluck=True)
	)
	return {extract_email_id(recipient).lower() for recipient in sent} & emails


def mark_bounced(emails: set[str]):
	"""Tick Email Bounced on every Email Address row holding one of *emails*, on any record.

	Each record's `modified` moves too, so a form opened before the bounce cannot save
	the box unticked again: Frappe refuses that save as made on an older copy.
	"""
	if not emails:
		return
	rows = frappe.get_all(
		EMAIL_DOCTYPE,
		filters={"email_address": ("in", list(emails)), "parenttype": ("in", CONTACT_PARENTS)},
		fields=["name", "parenttype", "parent"],
	)
	if not rows:
		return

	frappe.db.set_value(
		EMAIL_DOCTYPE, {"name": ("in", [row.name for row in rows])}, "is_bounced", 1, update_modified=False
	)
	modified = now_datetime()
	for parenttype in {row.parenttype for row in rows}:
		parents = [row.parent for row in rows if row.parenttype == parenttype]
		frappe.db.set_value(
			parenttype, {"name": ("in", parents)}, "modified", modified, update_modified=False
		)
