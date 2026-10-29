# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.utils.verified_command import verify_request

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	DESK,
	EMAIL,
	GIVEN,
	UNSUBSCRIBE_LINK,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS
from churchit.church_scope import is_multi_church, root_church
from churchit.contacts import primary_email

# Who stopped a church's emails is kept as Frappe's own Email Unsubscribe, made against the church.
UNSUBSCRIBE_REFERENCE = "Church"
UNSUBSCRIBE_METHOD = "/api/method/churchit.church_communications.newsletter.unsubscribe"


def email_church(church: str | None) -> str | None:
	"""The church a Church Email goes out in and whose unsubscribes apply: the root church on a single-church site."""
	return church if church and is_multi_church() else root_church()


def unsubscribed_emails(church: str) -> set[str]:
	"""Addresses that stopped *church*'s emails, or every email the site sends."""
	stopped = frappe.get_all(
		"Email Unsubscribe",
		filters={"reference_doctype": UNSUBSCRIBE_REFERENCE, "reference_name": church},
		pluck="email",
	)
	everything = frappe.get_all("Email Unsubscribe", filters={"global_unsubscribe": 1}, pluck="email")
	return set(stopped) | set(everything)


def is_subscribed(email: str, church: str) -> bool:
	return not frappe.db.exists("Email Unsubscribe", unsubscribe_filters(email, church))


def set_subscribed(email: str, church: str, subscribed: bool):
	"""Start or stop *church*'s emails to *email*.

	Stopping them withdraws Church News from each of the church's people holding the address.
	Starting them again records no consent here: the caller records the one person who asked.
	"""
	from churchit.church_communications import consent  # consent imports this module

	filters = unsubscribe_filters(email, church)
	if subscribed:
		frappe.db.delete("Email Unsubscribe", filters)
	elif not frappe.db.exists("Email Unsubscribe", filters):
		# Saved the usual way, an Email Unsubscribe writes the address onto the Church's timeline.
		unsubscribe = frappe.get_doc({"doctype": "Email Unsubscribe", **filters})
		unsubscribe.set_user_and_timestamp()
		unsubscribe.db_insert()
		# db_insert runs no hooks, so the consent hook is run here.
		consent.record_unsubscribe(unsubscribe)


def lift_global_unsubscribe(email: str):
	"""Let every email reach *email* again, for a member who asked for one in the portal."""
	frappe.db.delete("Email Unsubscribe", {"email": email, "global_unsubscribe": 1})


def unsubscribe_filters(email, church):
	return {"email": email, "reference_doctype": UNSUBSCRIBE_REFERENCE, "reference_name": church}


@frappe.whitelist(allow_guest=True)
def unsubscribe(
	email: str, church: str, purpose: str | None = None, person: str | None = None, **signed_params
):
	"""The link at the foot of every Church Email: stop that church's emails, or those for one purpose.

	A link with no purpose, or Church News, stops all of the church's emails to the address, as links
	always have. A purpose that no longer exists does the same, so the opt-out is still kept. *person*,
	signed into links sent since, is the person the copy went to, whatever their church.
	"""
	if not frappe.in_test and not verify_request():
		return

	church_name = frappe.db.get_value("Church", church, "church_name") or church
	if purpose and purpose != CHURCH_NEWS and frappe.db.exists("Communication Purpose", purpose):
		withdraw_purpose(email, church, purpose, person)
		message = _("{0} will no longer receive {1} emails from {2}.").format(email, _(purpose), church_name)
	else:
		set_subscribed(email, church, False)
		message = _("{0} will no longer receive emails from {1}.").format(email, church_name)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (a GET link does not auto-commit)
	frappe.respond_as_web_page(_("Unsubscribed"), message, indicator_color="green")


def withdraw_purpose(email: str, church: str, purpose: str, person: str | None = None):
	"""Withdraw Email for *purpose* from *person* and each of *church*'s people holding *email* who still allow it.

	A Group may hold another church's people, so the person the copy went to is named.
	"""
	from churchit.church_communications import consent  # consent imports this module

	people = consent.people_with_email(email, church)
	if person and person not in people:
		people.append(person)
	allowed = consent.allowed_people(people, EMAIL, purpose)
	record([holder for holder in people if holder in allowed], EMAIL, WITHDRAWN, purpose, UNSUBSCRIBE_LINK)


def has_unsubscribed(person) -> bool:
	"""Whether the church's emails no longer reach the loaded *person*'s primary email."""
	email = primary_email(person)
	return bool(email) and not is_subscribed(email, email_church(person.church))


def resubscribe(person):
	"""Let the church email the loaded *person* again, for someone who cannot do it in the portal."""
	if email := primary_email(person):
		set_subscribed(email, email_church(person.church), True)
		record([person.name], EMAIL, GIVEN, CHURCH_NEWS, DESK)
