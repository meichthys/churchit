# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""One person read from an import row, and the Address, Family and Person records it becomes.

A source module reads its row into an `ImportedPerson`; columns that carry Churchit's own fieldnames
(see `from_row`) need no code. A person is found again by the source system and their ID there, and a
family by its household ID, so a second import of the same people updates them instead of adding them again.
"""

from dataclasses import dataclass, field
from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, validate_email_address, validate_phone_number

from churchit.church_people import matching
from churchit.church_people.derived import BIRTH, DEATH
from churchit.church_scope import church_query_filters
from churchit.contacts import (
	ADDRESS_DOCTYPE,
	ADDRESS_FIELD,
	EMAIL_DOCTYPE,
	EMAIL_FIELD,
	PHONE_DOCTYPE,
	PHONE_FIELD,
	contact_key,
	get_other_holder,
)

PERSON_COLUMNS = (
	"prefix",
	"first_name",
	"middle_name",
	"last_name",
	"nickname",
	"suffix",
	"previous_last_name",
	"anniversary",
	"marital_status",
	"membership",
	"membership_status",
	"inactive_reason",
	"envelope_number",
	"medical_notes",
)
# Contact columns, and the Email or Phone Type each one stands for
EMAIL_COLUMNS = {"home_email": "Home", "work_email": "Work", "other_email": "Other"}
PHONE_COLUMNS = {"mobile_phone": "Mobile", "home_phone": "Home", "work_phone": "Work", "other_phone": "Other"}
ADDRESS_COLUMNS = ("address_line1", "address_line2", "city", "state", "pincode", "country")
HOME_ADDRESS_TYPE = "Home"
CANDIDATE_FIELDS = ("first_name", "last_name", "nickname", "middle_name", "birth_date", "gender", "family")


@dataclass
class Household:
	"""The household a person belongs to in the source system. *role* is a Family Members household role.

	A source that names no primary contact sets `may_be_primary_contact` instead: the person becomes the
	primary contact when the household has none yet. `address` is the household's address in the import
	file, which the provider works out from all its members' rows.
	"""

	legacy_id: str
	name: str | None = None
	role: str | None = None
	is_primary_contact: bool = False
	may_be_primary_contact: bool = False
	address: dict | None = None

	@property
	def may_lead(self) -> bool:
		return self.is_primary_contact or self.may_be_primary_contact


@dataclass
class ImportedPerson:
	"""One person from a source row, in Churchit's terms.

	`values` holds Person fields, and `address` Address fields. Each email and phone is (value, type), the
	type naming the Email or Phone Type its source column stands for.
	"""

	system: str
	legacy_id: str | None
	values: dict
	birth_date: date | None = None
	birth_year_unknown: bool = False
	is_deceased: bool = False
	emails: list[tuple[str, str]] = field(default_factory=list)
	phones: list[tuple[str, str]] = field(default_factory=list)
	address: dict | None = None
	household: Household | None = None

	@classmethod
	def from_row(
		cls, system: str, row: dict, gender: str | None, household: Household | None, **known
	) -> "ImportedPerson":
		"""Read the columns named with Churchit's fieldnames. The source works out *gender*, *household* and
		any other field it *knows*, such as `is_deceased`.

		A contact cell may hold several values separated by semicolons. A country may be a name or a code;
		a blank one is the site's country.
		"""
		address = {column: clean(row.get(column)) for column in ADDRESS_COLUMNS}
		address["country"] = (
			get_country(address["country"]) if address["country"] else frappe.db.get_default("country")
		)
		return cls(
			system=system,
			legacy_id=clean(row.get("legacy_id")),
			values={**{column: clean(row.get(column)) for column in PERSON_COLUMNS}, "gender": gender},
			birth_date=row.get("birth_date"),
			emails=split_contacts(row, EMAIL_COLUMNS),
			phones=split_contacts(row, PHONE_COLUMNS),
			address=address if address["address_line1"] else None,
			household=household,
			**known,
		)

	@property
	def key(self) -> tuple[str, str | None]:
		return (self.system, self.legacy_id)

	def insert_person(self, data_import: str) -> Document:
		"""Make the Person, with their Family and Address, and open a Possible Duplicate for anyone they may be."""
		person = frappe.new_doc("Person")
		person.update({"legacy_system": self.system, "legacy_id": self.legacy_id})
		self.save_person(person, data_import)
		self.record_possible_duplicates(person)
		return person

	def update_person(self, name: str, data_import: str) -> Document:
		"""Bring the imported Person *name* up to date. A blank column leaves a value alone; nothing is removed."""
		person = frappe.get_doc("Person", name)
		self.save_person(person, data_import)
		return person

	def save_person(self, person: Document, data_import: str):
		"""Save *person* and their household, each change marked in its history as made by *data_import*."""
		reference = {"doctype": "Data Import", "docname": data_import, "label": _("via Data Import")}
		family = self.get_family(reference)
		address = self.get_address(person, family)
		person.update({fieldname: value for fieldname, value in self.values.items() if value})
		if family:
			person.family = family.name
		self.set_birth(person)
		if self.is_deceased and not any(row.event_type == DEATH for row in person.life_events):
			person.append("life_events", {"event_type": DEATH})
		add_contacts(person, EMAIL_FIELD, EMAIL_DOCTYPE, "email_address", "email_type", self.valid_emails)
		add_contacts(person, PHONE_FIELD, PHONE_DOCTYPE, "phone_number", "phone_type", self.valid_phones)
		# The household keeps its address; a member living elsewhere keeps their own.
		is_household_address = bool(family and self.household.address) and (
			address_key(self.address) == address_key(self.household.address)
		)
		if address and not is_household_address and not has_address(person, address):
			add_address(person, address)
		person.flags.updater_reference = reference
		if person.is_new():
			person.insert()
		else:
			person.save()
		if family:
			self.place_in_household(person, family.name, address if is_household_address else None, reference)

	@property
	def valid_emails(self) -> list[tuple[str, str]]:
		return [(email, kind) for email, kind in self.emails if validate_email_address(email)]

	@property
	def valid_phones(self) -> list[tuple[str, str]]:
		return [(phone, kind) for phone, kind in self.phones if validate_phone_number(phone)]

	def set_birth(self, person: Document):
		"""Date the person's Birth life event, adding one when they have none."""
		if not self.birth_date:
			return
		birth = next((row for row in person.life_events if row.event_type == BIRTH), None)
		values = {"date": self.birth_date, "year_unknown": int(self.birth_year_unknown)}
		if birth:
			birth.update(values)
		else:
			person.append("life_events", {"event_type": BIRTH, **values})

	def get_family(self, reference: dict) -> Document | None:
		"""The Family imported for this person's household, made when its first member arrives."""
		if not self.household:
			return None
		name = get_imported_family(self.system, self.household.legacy_id)
		if name:
			return frappe.get_doc("Family", name)
		first_name, last_name = self.values["first_name"], self.values["last_name"]
		family = frappe.new_doc("Family")
		family.update(
			{
				# Person.household_name's form, "Last - First"
				"family_name": self.household.name or " - ".join(filter(None, (last_name, first_name))),
				"legacy_system": self.system,
				"legacy_id": self.household.legacy_id,
			}
		)
		family.flags.updater_reference = reference
		return family.insert()

	def get_address(self, person: Document, family: Document | None) -> str | None:
		"""The Address on the person or their family that is this one, else a new Address."""
		if not self.address:
			return None
		rows = [*person.get(ADDRESS_FIELD), *(family.get(ADDRESS_FIELD) if family else [])]
		known = frappe.get_all(
			"Address",
			filters={"name": ("in", [row.address for row in rows])},
			fields=["name", *ADDRESS_COLUMNS],
		)
		key = address_key(self.address)
		match = next((address.name for address in known if address_key(address) == key), None)
		if match:
			return match
		full_name = " ".join(filter(None, (self.values["first_name"], self.values["last_name"])))
		address = frappe.new_doc("Address")
		address.update({**self.address, "address_title": family.family_name if family else full_name})
		return address.insert().name

	def place_in_household(self, person: Document, family_name: str, address: str | None, reference: dict):
		"""Give the person their household role, and the household its primary contact and current *address*."""
		# Person.on_update has just put the person on the roster, so read the family again.
		family = frappe.get_doc("Family", family_name)
		member = next(row for row in family.members if row.member == person.name)
		if self.household.role:
			member.household_role = self.household.role
		if self.household.is_primary_contact or (
			self.household.may_be_primary_contact and not family.primary_contact
		):
			family.primary_contact = person.name
		if address and not has_address(family, address):
			add_address(family, address, current=True)
		family.flags.updater_reference = reference
		family.save()

	def record_possible_duplicates(self, person: Document):
		candidate = {fieldname: person.get(fieldname) for fieldname in CANDIDATE_FIELDS}
		candidate["emails"] = [row.email_address for row in person.emails]
		candidate["phones"] = [row.phone_number for row in person.phones]
		matches = matching.find_matches(candidate, church=person.church, exclude=person.name)
		matching.record_possible_duplicates(person.name, matches)


def get_imported_people(keys: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
	"""{(system, ID): Person} for the people already imported under *keys*, in the churches the importer holds.

	Another church's people are left out. The importer may not change them, and a source such as Rock RMS
	numbers each church's people from 1, so one ID can be two people.
	"""
	found = {}
	for system in {system for system, _legacy_id in keys}:
		people = frappe.get_all(
			"Person",
			filters={
				"legacy_system": system,
				"legacy_id": ("in", [legacy_id for key_system, legacy_id in keys if key_system == system]),
				**church_query_filters({}),
			},
			fields=["name", "legacy_id"],
			order_by="creation asc",
		)
		for person in people:
			found.setdefault((system, person.legacy_id), person.name)
	return found


def get_imported_family(system: str, legacy_id: str) -> str | None:
	"""The Family imported for the household *legacy_id* of *system*, in the churches the importer holds."""
	families = frappe.get_all(
		"Family",
		filters={"legacy_system": system, "legacy_id": legacy_id, **church_query_filters({})},
		pluck="name",
		order_by="creation asc",
		limit=1,
	)
	return families[0] if families else None


def add_contacts(
	doc: Document, fieldname: str, child_doctype: str, value_field: str, type_field: str, values
):
	"""Add each (value, type) of *values* that *doc* lacks, shared from whoever already holds it."""
	held = {contact_key(child_doctype, row.get(value_field)) for row in doc.get(fieldname)}
	for value, kind in values:
		key = contact_key(child_doctype, value)
		if key in held:
			continue
		held.add(key)
		doc.append(
			fieldname,
			{
				value_field: value,
				type_field: get_contact_type(child_doctype, type_field, kind),
				"shared_from_type": doc.doctype,
				"shared_from": get_other_holder(doc, child_doctype, value_field, value),
			},
		)


def add_address(doc: Document, address: str, current: bool = False):
	"""Add *address* to *doc*. A *current* one becomes its primary and mailing address."""
	address_type = get_contact_type(ADDRESS_DOCTYPE, "address_type", HOME_ADDRESS_TYPE)
	doc.append(
		ADDRESS_FIELD,
		{
			"address": address,
			"address_type": address_type,
			"is_primary": current,
			"is_mailing_address": current,
		},
	)


def has_address(doc: Document, address: str | None) -> bool:
	return any(row.address == address for row in doc.get(ADDRESS_FIELD))


def get_contact_type(child_doctype: str, type_field: str, preferred: str) -> str:
	"""*preferred* while the church keeps that type, else the type the contact table defaults to.

	Churches rename and remove types, so a source column only suggests one.
	"""
	df = frappe.get_meta(child_doctype).get_field(type_field)
	return preferred if frappe.db.exists(df.options, preferred) else df.default


def split_contacts(row: dict, columns: dict[str, str]) -> list[tuple[str, str]]:
	"""(value, type) for each value in *row*'s contact *columns*, a cell holding several split at semicolons."""
	return [
		(value, kind)
		for column, kind in columns.items()
		for value in filter(None, (clean(part) for part in cstr(row.get(column)).split(";")))
	]


def get_country(value: str) -> str | None:
	"""The Country named *value*, or whose code it is (US), or None when there is no such country."""
	if frappe.db.exists("Country", value):
		return frappe.db.get_value("Country", value, "name")
	return frappe.db.get_value("Country", {"code": value.lower()}, "name")


def address_key(address: dict) -> tuple:
	return tuple(cstr(address.get(column)).strip().lower() for column in ("address_line1", "city", "pincode"))


def clean(value) -> str | None:
	"""A cell's text without the spaces around it, or None when it is blank."""
	return cstr(value).strip() or None
