# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A signed-in member's own choices of how the church may contact them: the Communication Preferences page."""

import frappe
from frappe import _
from frappe.utils import sbool

from churchit.church_communications.consent import allowed
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	MEMBER_PORTAL,
	PUSH,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS
from churchit.church_communications.newsletter import email_church, lift_global_unsubscribe, set_subscribed
from churchit.church_communications.push import SUBSCRIPTION, is_push_on
from churchit.church_communications.sending import can_send_texts
from churchit.church_scope import session_church, session_person
from churchit.contacts import get_primary_email, get_primary_phone


def get_member_preferences() -> dict:
	"""What the signed-in member's page shows: their contact details and each purpose's switches."""
	church_name = frappe.db.get_value("Church", email_church(session_church()), "church_name")
	person = session_person()
	if not person:
		return {"person": None, "church_name": church_name}

	email = get_primary_email("Person", person)
	phone = get_primary_phone("Person", person)
	channels = get_channels(email, phone)
	purposes = frappe.get_all(
		"Communication Purpose", fields=["purpose", "description"], order_by="creation asc"
	)
	for row in purposes:
		row.allowed = {channel: allowed(person, channel, row.purpose) for channel in channels}
	return {
		"person": person,
		"church_name": church_name,
		"email": email,
		"phone": phone,
		"channels": channels,
		"purposes": purposes,
		"is_globally_unsubscribed": bool(email) and is_globally_unsubscribed(email),
	}


def get_channels(email: str | None, phone: str | None) -> list[str]:
	"""The channels the signed-in member can choose.

	Email with an address, texts with a phone once the site sends texts, and push notifications
	once push is on and a browser of theirs is subscribed.
	"""
	channels = [EMAIL] if email else []
	if phone and can_send_texts():
		channels.append(SMS)
	if is_push_on() and frappe.db.exists(SUBSCRIPTION, {"user": frappe.session.user}):
		channels.append(PUSH)
	return channels


def is_globally_unsubscribed(email: str) -> bool:
	"""True when *email* stopped every email the site sends."""
	return bool(frappe.db.exists("Email Unsubscribe", {"email": email, "global_unsubscribe": 1}))


@frappe.whitelist(methods=["POST"])
def set_preference(channel: str, purpose: str, allow: bool) -> dict:
	"""Record the signed-in member's yes or no to *channel* for *purpose*.

	It acts only on the session's own Person, so no caller can change another person's choices.
	"""
	person = session_person()
	if not person:
		frappe.throw(
			_("Your account is not linked to a member record. Please contact the church office."),
			frappe.PermissionError,
		)
	email = get_primary_email("Person", person)
	if channel not in get_channels(email, get_primary_phone("Person", person)):
		frappe.throw(_("You cannot choose {0} here.").format(channel))
	if not frappe.db.exists("Communication Purpose", purpose):
		frappe.throw(_("{0} is not a Communication Purpose.").format(purpose), frappe.DoesNotExistError)

	allow = sbool(allow)
	if channel == EMAIL:
		update_email_unsubscribes(email, email_church(session_church()), purpose, allow)
	record([person], channel, GIVEN if allow else WITHDRAWN, purpose, MEMBER_PORTAL)
	return {
		"message": get_saved_message(channel, purpose, allow),
		"is_globally_unsubscribed": bool(email) and is_globally_unsubscribed(email),
	}


def update_email_unsubscribes(email: str, church: str, purpose: str, allow: bool):
	"""Keep Frappe's Email Unsubscribe records in step with a member's email choice.

	Church News starts or stops the church's emails to the address. A yes to any purpose
	also lifts a stop on every email, because the member asked for this one.
	"""
	if purpose == CHURCH_NEWS:
		set_subscribed(email, church, allow)
	if allow:
		lift_global_unsubscribe(email)


def get_saved_message(channel: str, purpose: str, allow: bool) -> str:
	"""The alert the page shows once a switch is saved."""
	if channel == EMAIL:
		message = _("You will get {0} by email.") if allow else _("You will not get {0} by email.")
	elif channel == PUSH:
		message = (
			_("You will get {0} as a notification.")
			if allow
			else _("You will not get {0} as a notification.")
		)
	else:
		message = _("You will get {0} by text.") if allow else _("You will not get {0} by text.")
	return message.format(_(purpose))
