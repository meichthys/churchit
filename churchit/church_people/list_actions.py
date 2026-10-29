# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The actions on the people or households picked in the Person and Family lists, and so in a smart list.

Each function takes names from the browser, so it checks the caller's right on every record named.
"""

import frappe
from frappe import _

from churchit.church_communications.consent import allowed_people
from churchit.church_communications.doctype.church_email.church_email import CHOSEN_PEOPLE
from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL
from churchit.church_people.household import ADULT, members
from churchit.church_people.membership import INACTIVE
from churchit.contacts import get_primary_emails


@frappe.whitelist()
def get_people_emails(people: str | list[str]) -> frappe._dict:
	"""The primary emails of *people*, each address once, and the names of those with none or who refuse email."""
	people = get_permitted("Person", people, "email")
	allowed, refused = split_by_email_consent(people)
	result = get_email_list("Person", allowed, get_primary_emails("Person", allowed))
	result.refused = refused
	return result


@frappe.whitelist()
def get_household_emails(families: str | list[str]) -> frappe._dict:
	"""Each household's own email, else its primary contact's, and the households with neither."""
	families = get_permitted("Family", families, "email")
	emails = get_primary_emails("Family", families)
	# church-scope: only the families named, each checked above
	contacts = dict(
		frappe.get_all(
			"Family", filters={"name": ("in", families)}, fields=["name", "primary_contact"], as_list=True
		)
	)
	contact_emails = get_primary_emails(
		"Person", [contact for contact in contacts.values() if contact and may_email(contact)]
	)
	for family in families:
		emails[family] = emails.get(family) or contact_emails.get(contacts.get(family))
	return get_email_list("Family", families, emails)


@frappe.whitelist()
def get_household_adult_emails(people: str | list[str]) -> frappe._dict:
	"""The emails of the Adults in *people*'s households, each address once.

	Also names the Adults with no email or who refuse email, and those of *people* whose household
	has no Adult on file.
	"""
	people = get_permitted("Person", people, "email")
	# church-scope: only the people named, each checked above
	families = dict(
		frappe.get_all("Person", filters={"name": ("in", people)}, fields=["name", "family"], as_list=True)
	)
	adults_of = {
		family: [adult for adult in members(family, [ADULT]) if may_email(adult)]
		for family in set(filter(None, families.values()))
	}
	adults = list(dict.fromkeys(adult for found in adults_of.values() for adult in found))
	allowed, refused = split_by_email_consent(adults)
	result = get_email_list("Person", allowed, get_primary_emails("Person", allowed))
	result.refused = refused
	without_adults = [person for person in people if not adults_of.get(families[person])]
	titles = get_titles("Person", without_adults)
	result.without_adults = [titles[person] for person in without_adults]
	return result


@frappe.whitelist(methods=["POST"])
def new_church_email(people: str | list[str]) -> str:
	"""Start a draft Church Email to *people* and return its name, for the caller to write and send."""
	people = get_permitted("Person", people, "email")
	email = frappe.get_doc(
		{
			"doctype": "Church Email",
			"send_to": CHOSEN_PEOPLE,
			"people": [{"person": person} for person in people],
		}
	)
	# The subject and message are written on the form that opens next.
	email.flags.ignore_mandatory = True
	return email.insert().name


@frappe.whitelist(methods=["POST"])
def mark_inactive(people: str | list[str], reason: str) -> frappe._dict:
	"""Make each of *people* who is not Inactive yet Inactive for *reason*; Inactive Since is set on save."""
	if not frappe.db.exists("Inactive Reason", reason):
		frappe.throw(_("Pick an Inactive Reason."))
	docs = [frappe.get_doc("Person", person) for person in parse_names(people)]
	for doc in docs:
		doc.check_permission("write")

	active = [doc for doc in docs if doc.membership_status != INACTIVE]
	for doc in active:
		doc.membership_status = INACTIVE
		doc.inactive_reason = reason
		doc.save()
	return frappe._dict(marked=len(active), already_inactive=len(docs) - len(active))


def parse_names(names: str | list[str]) -> list[str]:
	"""Record names sent by the browser, each once, in the order given."""
	return list(dict.fromkeys(frappe.parse_json(names)))


def get_permitted(doctype: str, names: str | list[str], ptype: str) -> list[str]:
	"""*names* parsed, after refusing the whole call if the user may not *ptype* any one of them."""
	names = parse_names(names)
	for name in names:
		frappe.has_permission(doctype, ptype, doc=name, throw=True)
	return names


def may_email(person: str) -> bool:
	return frappe.has_permission("Person", "email", doc=person)


def split_by_email_consent(people: list[str]) -> tuple[list[str], list[str]]:
	"""*people* who allow email for every purpose, and the titles of those who do not."""
	allowed = allowed_people(people, EMAIL)
	refused = [person for person in people if person not in allowed]
	titles = get_titles("Person", refused)
	return [person for person in people if person in allowed], [titles[person] for person in refused]


def get_email_list(doctype: str, names: list[str], emails: dict[str, str]) -> frappe._dict:
	"""The addresses in *emails* ({name: address}) in the order of *names*, each once, and who has none."""
	without = [name for name in names if not emails.get(name)]
	titles = get_titles(doctype, without)
	return frappe._dict(
		emails=list(dict.fromkeys(emails[name] for name in names if emails.get(name))),
		without_email=[titles[name] for name in without],
	)


def get_titles(doctype: str, names: list[str]) -> dict[str, str]:
	"""{name: title} for *names*, records the caller was already allowed."""
	if not names:
		return {}
	title_field = frappe.get_meta(doctype).get_title_field()
	# church-scope: only records already permission-checked, by name
	rows = frappe.get_all(
		doctype, filters={"name": ("in", names)}, fields=["name", title_field], as_list=True
	)
	return {name: title or name for name, title in rows}
