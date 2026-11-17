# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import hmac

import frappe
from frappe import _
from frappe.utils import escape_html
from frappe.utils.verified_command import get_signed_params, verify_request

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	DESK,
	EMAIL,
	GIVEN,
	UNSUBSCRIBE_LINK,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHILD_SAFETY,
	CHURCH_NEWS,
)
from churchit.church_scope import is_multi_church, root_church
from churchit.contacts import primary_email

# Who stopped a church's emails is kept as Frappe's own Email Unsubscribe, made against the church.
UNSUBSCRIBE_REFERENCE = "Church"
UNSUBSCRIBE_METHOD = "/api/method/churchit.church_communications.newsletter.unsubscribe"
# Mail a church-wide unsubscribe never holds back.
REQUIRED_PURPOSES = (CHILD_SAFETY,)


def email_church(church: str | None) -> str | None:
	"""The church a Church Email goes out in and whose unsubscribes apply: the root church on a single-church site."""
	return church if church and is_multi_church() else root_church()


def unsubscribed_emails(church: str, purpose: str | None = None) -> set[str]:
	"""Addresses that stopped *church*'s emails, or every email the site sends.

	Mail for a required *purpose* is held back only by a stop on every email.
	"""
	stopped = []
	if purpose not in REQUIRED_PURPOSES:
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


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
def unsubscribe(
	email: str, church: str, purpose: str | None = None, person: str | None = None, **signed_params
) -> None:
	"""The link at the foot of every Church Email: stop that church's emails, or those for one purpose. Changes data.

	Opening the link (GET) shows a button and changes nothing, so a mail scanner that opens it
	unsubscribes no one. The button posts to the same signed link. A link for a purpose, Church News
	included, stops only that purpose. A link with no purpose, or one that no longer exists, stops all of
	the church's emails except required mail such as Child Safety. *person*, signed into links sent
	since, is the person the copy went to, whatever their church.
	"""
	if not frappe.in_test and not is_signed_link():
		return

	if not is_post():
		show_confirmation(email, church, purpose)
		return

	church_name = get_church_name(church)
	if withdraws_one_purpose(purpose):
		withdraw_purpose(email, church, purpose, person)
		message = _("{0} will no longer receive {1} emails from {2}.").format(email, _(purpose), church_name)
	else:
		set_subscribed(email, church, False)
		message = _("{0} will no longer receive emails from {1}.").format(email, church_name)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (a link does not auto-commit)
	way_back = _("To get them again, sign in and turn them on in Communication Preferences.")
	frappe.respond_as_web_page(
		_("Unsubscribed"),
		f"{escape_html(message)}<br><br>{way_back}",
		indicator_color="green",
		primary_action="/preferences",
		primary_label=_("Choose what you get"),
	)


def is_post() -> bool:
	return bool(frappe.request) and frappe.request.method == "POST"


def is_signed_link() -> bool:
	"""True when the request carries this site's signature for its query string, as a GET or a POST.

	Frappe's `verify_request` refuses a POST, so a POST is checked here against the same signature.
	"""
	if not is_post():
		return verify_request()

	query_string = frappe.safe_decode(frappe.request.query_string)
	params, separator, _signature = query_string.partition("&_signature=")
	if separator and hmac.compare_digest(get_signed_params(params), query_string):
		return True

	frappe.respond_as_web_page(
		_("Invalid Link"), _("This link is invalid or expired. Please make sure you have pasted correctly.")
	)
	return False


def show_confirmation(email: str, church: str, purpose: str | None):
	"""The page a GET opens: what the link stops, and a button that posts the same signed link."""
	church_name = get_church_name(church)
	if withdraws_one_purpose(purpose):
		question = _("Stop {0} emails from {1} to {2}?").format(_(purpose), church_name, email)
	else:
		question = _("Stop all emails from {0} to {1}?").format(church_name, email)
	action = escape_html(frappe.request.full_path if frappe.request else "")
	button = _("Unsubscribe")
	# A signed-in member's POST needs the session's CSRF token, as any desk or portal POST does.
	csrf_token = escape_html(frappe.session.data.csrf_token or "")
	frappe.respond_as_web_page(
		_("Unsubscribe"),
		f'{escape_html(question)}<br><br><form method="POST" action="{action}">'
		f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
		f'<button type="submit" class="btn btn-primary btn-sm btn-block">{escape_html(button)}</button></form>',
		indicator_color="orange",
		# The form's button is the one action, not Frappe's Home link.
		primary_action=None,
	)


def withdraws_one_purpose(purpose: str | None) -> bool:
	"""True when an unsubscribe link for *purpose* stops only that purpose, not all of the church's emails."""
	return bool(purpose and frappe.db.exists("Communication Purpose", purpose))


def get_unsubscribe_label(church: str | None, purpose: str | None) -> str:
	"""The words of the unsubscribe link in an email for *purpose*, true to what `unsubscribe` stops.

	Frappe puts the same words, unescaped, in the HTML link and in the plain text part, so they drop "<" and ">"
	and keep "&" as typed: a church named "Grace & Peace" reads the same in both parts.
	"""
	if withdraws_one_purpose(purpose):
		label = _("Unsubscribe from {0} emails").format(_(purpose))
	else:
		label = _("Unsubscribe from all {0} emails").format(get_church_name(church))
	return label.replace("<", "").replace(">", "")


def get_church_name(church: str | None) -> str:
	return (church and frappe.get_cached_value("Church", church, "church_name")) or church or _("church")


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
