# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Living people whose records need someone's attention, one row for each problem found."""

import frappe
from frappe import _
from frappe.utils import validate_email_address

from churchit.church_people.derived import CHILD
from churchit.church_people.matching import OPEN, POSSIBLE_DUPLICATE
from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.contacts import ADDRESS_DOCTYPE, EMAIL_DOCTYPE, PHONE_DOCTYPE, phone_digits
from churchit.utils import set_report_link_titles

NO_WAY_TO_REACH = "No Way to Reach"
INVALID_EMAIL = "Invalid Email"
INVALID_PHONE = "Invalid Phone Number"
EMAIL_BOUNCED = "Email Bounced"
MAIL_RETURNED = "Mail Returned"
POSSIBLE_DUPLICATE_OPEN = "Possible Duplicate"
CHILD_WITHOUT_BIRTH_DATE = "Child Without Birth Date"
NO_FAMILY = "No Family"
# A phone number has at least this many digits and, by the international standard (E.164), at most 15.
PHONE_DIGITS_RANGE = range(7, 16)


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{"fieldname": "problem", "fieldtype": "Data", "label": _("Problem"), "width": 180},
		{"fieldname": "detail", "fieldtype": "Data", "label": _("Detail"), "width": 260},
		{"fieldname": "family", "fieldtype": "Link", "label": _("Family"), "options": "Family", "width": 180},
	]


def get_data(filters):
	people = get_people(filters)
	if not people:
		return []

	checks = {
		NO_WAY_TO_REACH: get_people_with_no_way_to_reach,
		INVALID_EMAIL: get_invalid_emails,
		INVALID_PHONE: get_invalid_phones,
		EMAIL_BOUNCED: get_bounced_emails,
		MAIL_RETURNED: get_returned_mail,
		POSSIBLE_DUPLICATE_OPEN: get_open_duplicates,
		CHILD_WITHOUT_BIRTH_DATE: get_children_without_birth_date,
		NO_FAMILY: get_people_without_family,
	}
	if filters.get("problem"):
		checks = {filters["problem"]: checks[filters["problem"]]}

	rows = [
		{"person": person, "problem": _(problem), "detail": detail, "family": people[person].family}
		for problem, check in checks.items()
		for person, detail in check(people)
	]
	return sorted(rows, key=lambda row: people[row["person"]].full_name or "")


def get_people(filters) -> dict[str, frappe._dict]:
	"""The living people the reader may see, by name."""
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(Person.name, Person.full_name, Person.family, Person.life_stage, Person.birth_date)
		.where(living_people_filter(Person))
	)
	return {person.name: person for person in scoped(query, Person, filters).run(as_dict=True)}


def get_contact_rows(child_doctype: str, parenttype: str, parents, fields: list[str], **filters) -> list:
	if not parents:
		return []
	return frappe.get_all(
		child_doctype,
		filters={"parenttype": parenttype, "parent": ("in", list(parents)), **filters},
		fields=["parent", *fields],
	)


def get_people_with_no_way_to_reach(people):
	"""People with no email, phone or address of their own, in a family that has none either."""
	reachable, reachable_families = set(), set()
	families = {person.family for person in people.values() if person.family}
	for child_doctype in (EMAIL_DOCTYPE, PHONE_DOCTYPE, ADDRESS_DOCTYPE):
		reachable.update(row.parent for row in get_contact_rows(child_doctype, "Person", people, []))
		reachable_families.update(
			row.parent for row in get_contact_rows(child_doctype, "Family", families, [])
		)
	return [
		(name, None)
		for name, person in people.items()
		if name not in reachable and person.family not in reachable_families
	]


def get_invalid_emails(people):
	return [
		(row.parent, row.email_address)
		for row in get_contact_rows(EMAIL_DOCTYPE, "Person", people, ["email_address"])
		if not validate_email_address(row.email_address)
	]


def get_invalid_phones(people):
	return [
		(row.parent, row.phone_number)
		for row in get_contact_rows(PHONE_DOCTYPE, "Person", people, ["phone_number"])
		if len(phone_digits(row.phone_number)) not in PHONE_DIGITS_RANGE
	]


def get_bounced_emails(people):
	return [
		(row.parent, row.email_address)
		for row in get_contact_rows(EMAIL_DOCTYPE, "Person", people, ["email_address"], is_bounced=1)
	]


def get_returned_mail(people):
	return [
		(row.parent, row.address)
		for row in get_contact_rows(ADDRESS_DOCTYPE, "Person", people, ["address"], is_returned_mail=1)
	]


def get_open_duplicates(people):
	"""Each person in an open Possible Duplicate, with the other person's name."""
	pairs = frappe.get_all(
		POSSIBLE_DUPLICATE,
		filters={"status": OPEN},
		or_filters={"person": ("in", list(people)), "other_person": ("in", list(people))},
		fields=["person", "person_name", "other_person", "other_person_name"],
	)
	rows = []
	for pair in pairs:
		if pair.person in people:
			rows.append((pair.person, pair.other_person_name))
		if pair.other_person in people:
			rows.append((pair.other_person, pair.person_name))
	return rows


def get_children_without_birth_date(people):
	return [
		(name, None)
		for name, person in people.items()
		if person.life_stage == CHILD and not person.birth_date
	]


def get_people_without_family(people):
	return [(name, None) for name, person in people.items() if not person.family]
