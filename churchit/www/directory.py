# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import datetime

import frappe
from frappe import _
from frappe.utils import cint, formatdate

from churchit.church_foundations.doctype.church.church import address_line
from churchit.church_people.household import join_names
from churchit.church_people.membership import ACTIVE, CONTACT, VISITOR, living_people_filter
from churchit.church_scope import church_filters, session_church, session_person
from churchit.ics import calendar_text, fold

no_cache = 1
# A leap year, so that a birthday on 29 February has a date to format.
BIRTHDAY_YEAR = 2000


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/directory"
		raise frappe.Redirect

	if not cint(frappe.db.get_single_value("People Settings", "member_directory")):
		raise frappe.PageDoesNotExistError

	context.no_cache = 1
	context.show_sidebar = 1
	context.title = _("Member Directory")
	context.person = session_person()
	context.is_directory_member = bool(context.person) and is_directory_member(context.person)
	context.entries = get_entries(session_church()) if context.is_directory_member else []


def directory_filters(**filters) -> dict:
	"""Filters for the people the directory is for: active people who belong to the church.

	A visitor who filled in a card, or a contact, never chose to be shown to every member, so they
	are neither listed nor shown the list.
	"""
	return {"membership_status": ACTIVE, "membership": ("not in", (VISITOR, CONTACT)), **filters}


def is_directory_member(person: str) -> bool:
	"""True when the living *person* is one the directory is for, whether or not they hide from it."""
	# church-scope: one person, the viewer's own, by name
	return bool(
		frappe.get_all(
			"Person", filters=[directory_filters(name=person), living_people_filter()], limit=1, pluck="name"
		)
	)


def get_entries(church: str | None) -> list[frappe._dict]:
	"""The member directory of *church*: an entry for each family and for each person without one, by name."""
	people = frappe.get_all(
		"Person",
		filters=[
			church_filters(church, **directory_filters(hide_from_directory=0)),
			living_people_filter(),
		],
		fields=[
			"name",
			"first_name",
			"nickname",
			"last_name",
			"photo",
			"family",
			"birth_month",
			"birth_day",
			"share_email",
			"share_phone",
			"share_address",
			"share_birthday",
		],
		order_by="last_name asc, first_name asc",
	)
	details = get_shared_details(people)
	entries = [get_entry(family, household, details) for family, household in get_households(people)]
	return sorted(entries, key=lambda entry: entry.title.lower())


def get_households(people: list[frappe._dict]) -> list[tuple[frappe._dict | None, list[frappe._dict]]]:
	"""*people* by household: a family with its people, primary contact first and then in roster order, or one person."""
	names = list({person.family for person in people if person.family})
	# church-scope: only the families of the people listed, by name
	families = {
		family.name: family
		for family in frappe.get_all(
			"Family", filters={"name": ("in", names)}, fields=["name", "photo", "primary_contact"]
		)
	}
	roster = frappe.get_all(
		"Family Members", filters={"parenttype": "Family", "parent": ("in", names)}, fields=["member", "idx"]
	)
	places = {row.member: row.idx for row in roster}

	households = {}
	for person in people:
		households.setdefault(person.family or person.name, []).append(person)
	for key, household in households.items():
		if key in families:
			contact = families[key].primary_contact
			household.sort(key=lambda person: (person.name != contact, places.get(person.name, 0)))
	return [(families.get(key), household) for key, household in households.items()]


def get_entry(family: frappe._dict | None, people: list[frappe._dict], details: dict) -> frappe._dict:
	"""The directory entry of one household: its photo, its names and only the details each person shares."""
	shared = [details[person.name] for person in people]
	photos = [family.photo if family else None, *(person.photo for person in people)]
	names = [name for person in people for name in (person.first_name, person.nickname, person.last_name)]
	title = get_title(people)
	emails = unique(item.get("email") for item in shared)
	phones = unique(item.get("phone") for item in shared)
	addresses = unique(item.get("address") for item in shared)
	return frappe._dict(
		title=title,
		photo=next(filter(is_public, photos), None),
		emails=emails,
		phones=phones,
		addresses=addresses,
		vcard=get_vcard(title, emails, phones, addresses),
		birthdays=[
			f"{person.nickname or person.first_name} {item['birthday']}"
			for person, item in zip(people, shared, strict=True)
			if item.get("birthday")
		],
		search=" ".join(filter(None, names)).lower(),
	)


def get_vcard(title: str, emails: list[str], phones: list[str], addresses: list[str]) -> str:
	"""A vCard 3.0 contact of one entry, with only the details the entry shows. An address goes in the street part."""
	name = calendar_text(title)
	lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{name};;;;", f"FN:{name}"]
	lines += [f"EMAIL;TYPE=INTERNET:{calendar_text(email)}" for email in emails]
	lines += [f"TEL:{calendar_text(phone)}" for phone in phones]
	lines += [f"ADR:;;{calendar_text(address)};;;;" for address in addresses]
	lines.append("END:VCARD")
	return "\r\n".join(fold(line) for line in lines) + "\r\n"


def get_title(people: list[frappe._dict]) -> str:
	"""How the directory names a household: "Johnson, Robert & Mary", or "Robert Johnson & Mary Lee" across last names."""
	first_names = [person.nickname or person.first_name for person in people]
	last_names = {person.last_name or "" for person in people}
	if len(last_names) > 1:
		return join_names(
			[
				f"{first_name} {person.last_name or ''}".strip()
				for first_name, person in zip(first_names, people, strict=True)
			]
		)
	last_name = last_names.pop()
	return f"{last_name}, {join_names(first_names)}" if last_name else join_names(first_names)


def get_shared_details(people: list[frappe._dict]) -> dict[str, dict]:
	"""{person: {"email", "phone", "address", "birthday"}} holding only what each of *people* ticked to share."""
	emails = get_primary_emails([person.name for person in people if person.share_email])
	phones = get_primary_phones([person.name for person in people if person.share_phone])
	addresses = get_mailing_addresses([person for person in people if person.share_address])
	details = {}
	for person in people:
		details[person.name] = {
			"email": emails.get(person.name),
			"phone": phones.get(person.name),
			"address": addresses.get(person.name),
		}
		if person.share_birthday and person.birth_month and person.birth_day:
			birthday = datetime.date(BIRTHDAY_YEAR, person.birth_month, person.birth_day)
			details[person.name]["birthday"] = formatdate(birthday, "MMM d")
	return details


def get_primary_emails(people: list[str]) -> dict[str, str]:
	"""{person: primary email} of *people*. A primary row is read last, so it wins; without one the first does."""
	rows = frappe.get_all(
		"Email Address",
		filters={"parenttype": "Person", "parent": ("in", people)},
		fields=["parent", "email_address"],
		order_by="is_primary asc, idx desc",
	)
	return {row.parent: row.email_address for row in rows}


def get_primary_phones(people: list[str]) -> dict[str, str]:
	"""{person: primary phone} of *people*, chosen as `get_primary_emails` chooses."""
	rows = frappe.get_all(
		"Phone Number",
		filters={"parenttype": "Person", "parent": ("in", people)},
		fields=["parent", "phone_number"],
		order_by="is_primary asc, idx desc",
	)
	return {row.parent: row.phone_number for row in rows}


def get_mailing_addresses(people: list[frappe._dict]) -> dict[str, str]:
	"""{person: one-line mailing address} of *people*: their own, else their family's.

	The row marked for mail wins, then the primary one, then the first, as `contacts.mailing_address` decides.
	"""
	parents = [*(person.name for person in people), *(person.family for person in people if person.family)]
	rows = frappe.get_all(
		"Postal Address",
		filters={"parenttype": ("in", ["Person", "Family"]), "parent": ("in", parents)},
		fields=["parent", "address"],
		order_by="is_mailing_address asc, is_primary asc, idx desc",
	)
	mailing = {row.parent: row.address for row in rows}
	addresses = frappe.get_all(
		"Address",
		filters={"name": ("in", list(mailing.values()))},
		fields=["name", "address_line1", "address_line2", "city", "state", "pincode"],
	)
	lines = {address.name: address_line(address) for address in addresses}
	found = {person.name: mailing.get(person.name) or mailing.get(person.family) for person in people}
	return {person: lines[address] for person, address in found.items() if address in lines}


def is_public(url: str | None) -> bool:
	"""True for a photo every member may load: a private file opens only for those who may read its record."""
	return bool(url) and not url.startswith("/private/")


def unique(values) -> list:
	"""*values* without blanks and repeats, in order."""
	return list(dict.fromkeys(filter(None, values)))
