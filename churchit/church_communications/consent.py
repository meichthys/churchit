# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Whether the church may contact a person on a channel, for a purpose.

Communication Consent records are the one owner of the answer. Email Unsubscribe stays
Frappe's own record, so Frappe's email queue keeps honouring it, and each one also
withdraws consent here.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, get_url, getdate
from frappe.utils.verified_command import get_signed_params, verify_request

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	EMAIL_LINK,
	GIVEN,
	PHONE,
	PUSH,
	SMS,
	UNSUBSCRIBE_LINK,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS
from churchit.church_communications.newsletter import UNSUBSCRIBE_REFERENCE, email_church
from churchit.church_people.membership import living_people_filter
from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, contact_key

RENEW_METHOD = "/api/method/churchit.church_communications.consent.renew_consent"

# The contact table and column that hold a channel's addresses, compared by contacts.contact_key.
CONTACT_COLUMNS = {
	EMAIL: (EMAIL_DOCTYPE, "email_address"),
	SMS: (PHONE_DOCTYPE, "digits"),
	PHONE: (PHONE_DOCTYPE, "digits"),
}


def allowed(person: str, channel: str, purpose: str | None = None) -> bool:
	"""True when the church may contact *person* on *channel* for *purpose* (None: no particular purpose)."""
	return person in allowed_people([person], channel, purpose)


def allowed_people(people: list[str], channel: str, purpose: str | None = None) -> set[str]:
	"""The people among *people* whom the church may contact on *channel* for *purpose*.

	Nobody who has died is contacted. Otherwise the newest record for the channel decides,
	whether it names this purpose or is blank for every purpose, but a yes for every purpose
	never undoes a no for this one. With no record, nobody gets texts or push notifications, and
	the person's church decides the other channels. A few queries answer for any number of people.
	"""
	people = [person for person in people if person]
	if not people:
		return set()
	# church-scope: deciding for people the caller already chose; nothing here is shown
	living = frappe.get_all(
		"Person", filters=[{"name": ("in", people)}, living_people_filter()], fields=["name", "church"]
	)
	statuses = default_statuses(living, channel) | latest_statuses(people, channel, purpose)
	return {row.name for row in living if statuses[row.name] == GIVEN}


def default_statuses(people: list[frappe._dict], channel: str) -> dict[str, str]:
	"""Each person's status with no record.

	Texts need a yes first, as carriers and the law require, and push notifications too. On other
	channels it is Withdrawn only where the person's church contacts people only with consent.
	"""
	if channel in (SMS, PUSH):
		return {row.name: WITHDRAWN for row in people}
	asks_first = set(frappe.get_all("Church", filters={"contact_only_with_consent": 1}, pluck="name"))
	churches = {church: email_church(church) for church in {row.church for row in people}}
	return {row.name: WITHDRAWN if churches[row.church] in asks_first else GIVEN for row in people}


def latest_statuses(people: list[str], channel: str, purpose: str | None = None) -> dict[str, str]:
	"""Each person's newest status on *channel* for *purpose* or for every purpose.

	At the same Recorded On the later entry wins. A yes for every purpose is skipped while
	a no for *purpose* stands: only a later yes for *purpose* undoes that.
	"""
	Consent = frappe.qb.DocType("Communication Consent")
	purposes = Consent.purpose.isnull() | (Consent.purpose == "")
	if purpose:
		purposes |= Consent.purpose == purpose
	# church-scope: a person's consent counts wherever it was recorded
	rows = (
		frappe.qb.from_(Consent)
		.select(Consent.person, Consent.purpose, Consent.status)
		.where(Consent.person.isin(people) & (Consent.channel == channel) & purposes)
		.orderby(Consent.recorded_on)
		.orderby(Consent.creation)
		.run(as_dict=True)
	)

	statuses: dict[str, str] = {}
	withdrawn_for_purpose: set[str] = set()
	for row in rows:
		if row.purpose and row.status == WITHDRAWN:
			withdrawn_for_purpose.add(row.person)
		elif row.purpose:
			withdrawn_for_purpose.discard(row.person)
		elif row.status == GIVEN and row.person in withdrawn_for_purpose:
			continue
		statuses[row.person] = row.status
	return statuses


def refused_values(values: list[str], channel: str) -> set[str]:
	"""The email addresses or phone numbers among *values* that no one holding them lets the church use.

	A shared address keeps reaching anyone holding it who may be contacted on *channel*.
	An address that no Person holds is never refused.
	"""
	holders = holders_by_key(values, channel)
	reachable = allowed_people(list(set().union(*holders.values())), channel)
	child_doctype = CONTACT_COLUMNS[channel][0]
	return {
		value
		for value in values
		if (people := holders.get(contact_key(child_doctype, value))) and not people & reachable
	}


def holders_by_key(values: list[str], channel: str) -> dict[str, set[str]]:
	"""Map each address's comparison key to the people holding it, shared rows included."""
	child_doctype, column = CONTACT_COLUMNS[channel]
	keys = {contact_key(child_doctype, value) for value in values if value}
	if not keys:
		return {}
	rows = frappe.get_all(
		child_doctype, filters={"parenttype": "Person", column: ("in", list(keys))}, fields=["parent", column]
	)
	holders: dict[str, set[str]] = {}
	for row in rows:
		holders.setdefault(contact_key(child_doctype, row[column]), set()).add(row.parent)
	return holders


def people_with_email(email: str, church: str | None = None) -> list[str]:
	"""Everyone holding *email*; only the people of *church* when it is given."""
	people = holders_by_key([email], EMAIL).get(contact_key(EMAIL_DOCTYPE, email), set())
	if church and people:
		# church-scope: a church's unsubscribe concerns its own people, found here by name
		rows = frappe.get_all("Person", filters={"name": ("in", list(people))}, fields=["name", "church"])
		people = {row.name for row in rows if email_church(row.church) == church}
	return sorted(people)


def record_unsubscribe(doc, method=None):
	"""after_insert on Email Unsubscribe: withdraw Email from everyone holding the address.

	A global unsubscribe withdraws every purpose, and a church's unsubscribe withdraws its
	own people's Church News. One that leaves a single conversation says nothing about
	consent. People already withdrawn since are skipped, so the backfill can run again.
	"""
	if doc.global_unsubscribe:
		purpose, people = None, people_with_email(doc.email)
	elif doc.reference_doctype == UNSUBSCRIBE_REFERENCE:
		purpose, people = CHURCH_NEWS, people_with_email(doc.email, doc.reference_name)
	else:
		return
	done = withdrawn_since(people, purpose, doc.creation)
	record(
		[person for person in people if person not in done],
		EMAIL,
		WITHDRAWN,
		purpose,
		UNSUBSCRIBE_LINK,
		doc.creation,
	)


def withdrawn_since(people: list[str], purpose: str | None, since) -> set[str]:
	"""The people among *people* with an Email withdrawal for exactly *purpose* recorded at or after *since*."""
	if not people:
		return set()
	# church-scope: a person's own records, looked up by name
	return set(
		frappe.get_all(
			"Communication Consent",
			filters={
				"person": ("in", people),
				"channel": EMAIL,
				"purpose": purpose or ("is", "not set"),
				"status": WITHDRAWN,
				"recorded_on": (">=", since),
			},
			pluck="person",
		)
	)


def is_due_for_renewal(doc) -> bool:
	"""True when *doc* is a living person's newest Email record, a yes, in a church that contacts only with consent.

	A newer record, a yes renewed or a no, ends it, so a person is asked once for each yes they give.
	"""
	if doc.channel != EMAIL or doc.status != GIVEN:
		return False
	if not frappe.db.get_value("Church", email_church(doc.church), "contact_only_with_consent"):
		return False
	if frappe.db.get_value("Person", doc.person, "is_deceased"):
		return False
	recorded_on = get_datetime(doc.recorded_on)
	# church-scope: one person's own records, by name
	others = frappe.get_all(
		"Communication Consent",
		filters={
			"person": doc.person,
			"channel": EMAIL,
			"recorded_on": (">=", recorded_on),
			"name": ("!=", doc.name),
		},
		fields=["recorded_on", "creation"],
	)
	creation = get_datetime(doc.creation)
	return not any(row.recorded_on > recorded_on or row.creation > creation for row in others)


def consent_renewal_link(doc) -> str:
	"""Jinja: the signed "Yes, keep in touch" link of the Consent Renewal email."""
	return get_url(f"{RENEW_METHOD}?{get_signed_params({'person': doc.person})}")


@frappe.whitelist(allow_guest=True)
def renew_consent(person: str, **signed_params):
	"""The "Yes, keep in touch" link: say yes again to everything the person allows by email."""
	if not frappe.in_test and not verify_request():
		return

	renew(person)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (a GET link does not auto-commit)
	church = email_church(frappe.db.get_value("Person", person, "church"))
	frappe.respond_as_web_page(
		_("Thank you"),
		_("{0} will keep in touch with you by email.").format(
			frappe.db.get_value("Church", church, "church_name") or church
		),
		indicator_color="green",
	)


def renew(person: str) -> list[str]:
	"""Record again each email yes the person's newest records hold, once a day however often the link is opened."""
	# church-scope: one person's own records, by name
	rows = frappe.get_all(
		"Communication Consent",
		filters={"person": person, "channel": EMAIL},
		fields=["purpose", "status", "method", "recorded_on"],
		order_by="recorded_on asc, creation asc",
	)
	newest = {row.purpose or None: row for row in rows}
	purposes = [
		purpose
		for purpose, row in newest.items()
		if row.status == GIVEN and not (row.method == EMAIL_LINK and getdate(row.recorded_on) == getdate())
	]
	return [name for purpose in purposes for name in record([person], EMAIL, GIVEN, purpose, EMAIL_LINK)]
