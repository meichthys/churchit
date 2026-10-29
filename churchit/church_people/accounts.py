# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Portal accounts and the people they belong to.

A Website User who signs in proves they hold their email address, because Frappe
sends a new account a link to set its password; there is no other proof to wait for.
"""

import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce

from churchit.church_ministries.kiosk import KIOSK_ROLE
from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.matching import (
	Profile,
	compare,
	find_matches,
	get_people,
	record_possible_duplicates,
)
from churchit.church_people.member_access import is_portal_member
from churchit.church_people.membership import VISITOR, living_people_filter
from churchit.church_scope import scoped, session_person
from churchit.contacts import EMAIL_DOCTYPE, EMAIL_FIELD, get_other_holder

# The Person source of the people added for a portal login.
PORTAL = "Portal"


def link_portal_user(login_manager=None):
	"""on_session_creation: give a Website User who signs in with no Person one.

	The one person of the user's churches who holds the address as their own primary
	email and has no login is linked. With none, a Visitor is added and the people
	who may be them are left for the office. With several, nobody is linked and the
	office sorts them out. A linked user costs one query on every later sign-in.
	A self check-in kiosk is a device, not a person, so it gets none.
	"""
	user = frappe.session.user
	if not is_portal_member(user) or session_person() or KIOSK_ROLE in frappe.get_roles(user):
		return

	# A failed link must not stop the sign-in; the next sign-in tries again.
	frappe.db.savepoint("link_portal_user")
	try:
		find_or_add_person(user)
	except Exception as error:
		if isinstance(error, frappe.QueryDeadlockError):
			# The database has rolled back the whole transaction, and the savepoint with it.
			frappe.db.rollback()
		else:
			frappe.db.rollback(save_point="link_portal_user")
		frappe.log_error(_("Could not link the portal login {0} to a Person").format(user))


def find_or_add_person(user: str) -> None:
	"""Link *user* to the person who holds their address, add one, or leave the several who hold it for the office."""
	details = frappe.db.get_value("User", user, ["email", "first_name", "last_name"], as_dict=True)
	holders = get_unlinked_holders(details.email)
	if len(holders) == 1:
		link_person(holders[0], user)
	elif holders:
		record_holders_as_duplicates(holders)
	else:
		add_person(user, details)


def get_unlinked_holders(email: str) -> list[str]:
	"""Living people of the session user's churches with *email* as their own primary address and no login."""
	Person = frappe.qb.DocType("Person")
	Email = frappe.qb.DocType(EMAIL_DOCTYPE)
	query = (
		frappe.qb.from_(Person)
		.join(Email)
		.on(
			(Email.parent == Person.name)
			& (Email.parenttype == "Person")
			& (Email.parentfield == EMAIL_FIELD)
		)
		.select(Person.name)
		.distinct()
		.where((Email.email_address == email) & (Email.is_primary == 1))
		.where(Coalesce(Email.shared_from, "") == "")
		.where(Coalesce(Person.user, "") == "")
		.where(living_people_filter(Person))
		.orderby(Person.name)
	)
	return scoped(query, Person, {}).run(pluck=True)


def link_person(person: str, user: str) -> None:
	"""Set *user* as the portal login of *person*, and point the user's church at the person's.

	The user is the session's portal member, who may not change their own Portal User
	through a save, so the field is set directly.
	"""
	doc = frappe.get_doc("Person", person)
	doc.db_set("user", user)
	doc.sync_church_permission()


def add_person(user: str, details: frappe._dict) -> str:
	"""Add a Visitor for *user*, in the church the user signed up at, and record who they may duplicate.

	An address another person holds is shared from them, as on a Connection Card.
	"""
	person = frappe.get_doc(
		{
			"doctype": "Person",
			"first_name": details.first_name,
			"last_name": details.last_name,
			"membership": VISITOR,
			"source": PORTAL,
			"user": user,
			# They never saw the member directory's choices, so they share nothing in it.
			**dict.fromkeys(SHARE_DEFAULTS, 0),
		}
	)
	person.append(
		EMAIL_FIELD,
		{
			"email_address": details.email,
			"shared_from_type": person.doctype,
			"shared_from": get_other_holder(person, EMAIL_DOCTYPE, "email_address", details.email),
		},
	)
	person.flags.from_portal_login = True
	person.insert(ignore_permissions=True)

	candidate = {"first_name": details.first_name, "last_name": details.last_name, "emails": [details.email]}
	record_possible_duplicates(
		person.name, find_matches(candidate, church=person.church, exclude=person.name)
	)
	return person.name


def record_holders_as_duplicates(holders: list[str]) -> None:
	"""Pair the first of the people who hold one address with each of the others, scored by the matcher."""
	# church-scope: names people get_unlinked_holders found inside the user's churches
	Person = frappe.qb.DocType("Person")
	first, *others = get_people(condition=Person.name.isin(holders))
	profile = Profile.from_record(first)
	record_possible_duplicates(
		first.name, [compare(profile, Profile.from_record(other), other.name) for other in others]
	)
