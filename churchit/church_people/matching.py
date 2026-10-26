# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Find the people a record may duplicate.

`find_matches` is the one matcher. The new-Person warning in the desk, the weekly duplicate scan and the
people imports all call it, so they agree on who is the same person. A `Match` names an existing person,
a score from 0 to 100 and the reasons that scored, such as "same email" or "nickname of first name". A
person counts as a match when the score reaches People Settings' match threshold.

A candidate is a dict of Person fields (`first_name`, `last_name`, `nickname`, `middle_name`,
`birth_date`, `gender`, `family`) plus `emails` and `phones`, each a list of strings as typed.

Each reason carries a weight in `WEIGHTS`. Agreement adds up to at most 100 and each conflict then takes
points away, so a different birth date or a different first name outweighs a shared family phone.
"""

import difflib
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import cache

import frappe
from frappe import _
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Coalesce
from frappe.utils import cint, cstr, getdate

from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.membership import VISITOR, living_people_filter
from churchit.church_scope import church_filters
from churchit.contacts import (
	EMAIL_DOCTYPE,
	EMAIL_FIELD,
	PHONE_DOCTYPE,
	PHONE_FIELD,
	get_other_holder,
	phone_digits,
)

POSSIBLE_DUPLICATE = "Possible Duplicate"
OPEN = "Open"
MERGED = "Merged"
NOT_A_DUPLICATE = "Not a Duplicate"

DEFAULT_THRESHOLD = 80
WEIGHTS = {
	"same email": 45,
	"same phone": 30,
	"same birth date": 30,
	"same first name": 35,
	"nickname of first name": 30,
	"similar first name": 20,
	"same first initial": 15,
	"same last name": 20,
	"matches previous last name": 15,
	"shares part of last name": 15,
	"different first name": -50,
	"different birth date": -40,
	"different gender": -40,
	"different suffix": -40,
}
# A common last name can bring back a whole congregation; score no more than this many people per call.
MAX_CANDIDATES = 500
# The shortest phone number worth comparing, and how many trailing digits two numbers must share: enough
# that a country code or a trunk 0 typed on one of them does not matter.
MIN_PHONE_DIGITS = 7
PHONE_TAIL = 10
# How alike two first names must be, from difflib, to count as one name spelled two ways ("Jon", "John").
SIMILAR_NAME_RATIO = 0.8
SUFFIXES = frozenset(("jr", "sr", "ii", "iii", "iv", "v"))
GENDERS = ("Female", "Male")
PERSON_FIELDS = (
	"name",
	"first_name",
	"last_name",
	"nickname",
	"middle_name",
	"previous_last_name",
	"suffix",
	"birth_date",
	"gender",
	"family",
)
NICKNAMES_FILE = os.path.join(os.path.dirname(__file__), "nicknames.json")


@dataclass(frozen=True)
class Match:
	person: str
	score: int
	reasons: tuple[str, ...] = field(default=())


def find_matches(
	candidate: dict, church: str | None = None, limit: int = 5, exclude: str | None = None
) -> list[Match]:
	"""Living people who may be *candidate*, best first, scoring at or above the match threshold.

	*church* narrows to that church's people, and *exclude* leaves out one person, such as the candidate itself.
	"""
	profile = Profile.from_record(candidate)
	condition = profile.get_narrowing_condition()
	if condition is None:
		return []

	threshold = get_match_threshold()
	people = get_people(church, condition, exclude=exclude, limit=MAX_CANDIDATES)
	matches = [compare(profile, Profile.from_record(person), person.name) for person in people]
	matches = [match for match in matches if match.score >= threshold]
	return sorted(matches, key=lambda match: (-match.score, match.person))[:limit]


def get_match_threshold() -> int:
	return cint(frappe.db.get_single_value("People Settings", "match_threshold")) or DEFAULT_THRESHOLD


def get_people(
	church: str | None = None,
	condition: Criterion | None = None,
	exclude: str | None = None,
	limit: int | None = None,
) -> list[frappe._dict]:
	"""Living people of *church* (of every church when None) meeting *condition*, as candidates.

	Each carries the emails and phones that are its own. A row shared from another record is that
	record's contact, the way the contact tables treat it.
	"""
	Person = frappe.qb.DocType("Person")
	query = frappe.qb.get_query(
		"Person", fields=list(PERSON_FIELDS), filters=church_filters(church), limit=limit
	).where(living_people_filter(Person))
	if condition is not None:
		query = query.where(condition)
	if exclude:
		query = query.where(Person.name != exclude)
	people = query.run(as_dict=True)

	names = [person.name for person in people]
	emails = get_own_contacts(EMAIL_DOCTYPE, EMAIL_FIELD, "email_address", names)
	phones = get_own_contacts(PHONE_DOCTYPE, PHONE_FIELD, "phone_number", names)
	for person in people:
		person.emails = emails.get(person.name, [])
		person.phones = phones.get(person.name, [])
	return people


def get_own_contacts(child_doctype: str, parentfield: str, value_field: str, people: list[str]) -> dict:
	"""Map ``{person: [values]}`` of one contact table, leaving out rows shared from another record."""
	if not people:
		return {}
	rows = frappe.get_all(
		child_doctype,
		filters={
			"parenttype": "Person",
			"parentfield": parentfield,
			"parent": ("in", people),
			"shared_from": ("is", "not set"),
		},
		fields=["parent", value_field],
	)
	contacts: dict[str, list[str]] = {}
	for row in rows:
		contacts.setdefault(row.parent, []).append(row[value_field])
	return contacts


@dataclass(frozen=True)
class Profile:
	"""What the matcher compares about one person: names and contacts normalized, and details."""

	first_name: str
	nickname: str
	last_name_parts: tuple[str, ...]
	previous_last_name: str
	suffix: str
	emails: frozenset[str]
	phones: tuple[str, ...]
	birth_date: date | None
	gender: str
	last_names_as_typed: tuple[str, ...]

	@classmethod
	def from_record(cls, record: dict) -> "Profile":
		last_name_words = name_words(record.get("last_name"))
		return cls(
			first_name=name_key(record.get("first_name")),
			nickname=name_key(record.get("nickname")),
			last_name_parts=tuple(word for word in last_name_words if word not in SUFFIXES),
			previous_last_name=name_key(record.get("previous_last_name")),
			suffix=name_key(record.get("suffix")) or "".join(w for w in last_name_words if w in SUFFIXES),
			emails=frozenset(cstr(email).strip().lower() for email in record.get("emails") or [] if email),
			phones=tuple(filter(None, (phone_digits(cstr(phone)) for phone in record.get("phones") or []))),
			birth_date=getdate(record["birth_date"]) if record.get("birth_date") else None,
			gender=cstr(record.get("gender")),
			last_names_as_typed=get_last_name_variants(
				record.get("last_name"), record.get("previous_last_name")
			),
		)

	@property
	def last_name(self) -> str:
		return "".join(self.last_name_parts)

	@property
	def given_names(self) -> tuple[str, ...]:
		return tuple(filter(None, (self.first_name, self.nickname)))

	def get_narrowing_condition(self) -> Criterion | None:
		"""The lookups that pick the people worth scoring: same last name, email or phone, or a nickname and birthday."""
		# church-scope: builds a criterion and reads nothing; get_people runs it inside the church it is given
		Person = frappe.qb.DocType("Person")
		conditions = []
		if self.last_names_as_typed:
			names = self.last_names_as_typed
			conditions.append(Person.last_name.isin(names) | Person.previous_last_name.isin(names))
		if self.emails:
			Email = frappe.qb.DocType(EMAIL_DOCTYPE)
			conditions.append(Person.name.isin(holders_query(Email, Email.email_address.isin(self.emails))))
		phone_tails = {phone[-MIN_PHONE_DIGITS:] for phone in self.phones if len(phone) >= MIN_PHONE_DIGITS}
		if phone_tails:
			Phone = frappe.qb.DocType(PHONE_DOCTYPE)
			matching_tail = Criterion.any(Phone.digits.like(f"%{tail}") for tail in phone_tails)
			conditions.append(Person.name.isin(holders_query(Phone, matching_tail)))
		if self.birth_date and self.given_names:
			first_names = sorted({name for given in self.given_names for name in get_nickname_group(given)})
			conditions.append(
				(Person.birth_date == self.birth_date)
				& (Person.first_name.isin(first_names) | Person.nickname.isin(first_names))
			)
		return Criterion.any(conditions) if conditions else None


def holders_query(Child, condition: Criterion):
	"""Subquery for the people holding a contact row of the *Child* table meeting *condition* as their own."""
	return (
		frappe.qb.from_(Child)
		.select(Child.parent)
		.where(Child.parenttype == "Person")
		.where(Coalesce(Child.shared_from, "") == "")
		.where(condition)
	)


def compare(candidate: Profile, other: Profile, person: str) -> Match:
	"""Score how likely *other* is the same person as *candidate*."""
	reasons = [
		*compare_first_names(candidate, other),
		*compare_last_names(candidate, other),
		*compare_contacts(candidate, other),
		*compare_details(candidate, other),
	]
	agreement = min(sum(WEIGHTS[reason] for reason in reasons if WEIGHTS[reason] > 0), 100)
	conflict = sum(WEIGHTS[reason] for reason in reasons if WEIGHTS[reason] < 0)
	return Match(person, max(agreement + conflict, 0), tuple(reasons))


def compare_first_names(candidate: Profile, other: Profile) -> list[str]:
	if not candidate.first_name or not other.first_name:
		return []
	if candidate.first_name == other.first_name:
		return ["same first name"]
	pairs = [(mine, theirs) for mine in candidate.given_names for theirs in other.given_names]
	if any(theirs in get_nickname_group(mine) for mine, theirs in pairs):
		return ["nickname of first name"]
	if any(is_similar(mine, theirs) for mine, theirs in pairs):
		return ["similar first name"]
	if is_initial_of(candidate.first_name, other.first_name) or is_initial_of(
		other.first_name, candidate.first_name
	):
		return ["same first initial"]
	return ["different first name"]


def compare_last_names(candidate: Profile, other: Profile) -> list[str]:
	if not candidate.last_name or not other.last_name:
		return []
	if candidate.last_name == other.last_name:
		return ["same last name"]
	if candidate.last_name == other.previous_last_name or other.last_name == candidate.previous_last_name:
		return ["matches previous last name"]
	shared = set(candidate.last_name_parts) & set(other.last_name_parts)
	if any(len(part) >= 3 for part in shared):
		return ["shares part of last name"]
	return []


def compare_contacts(candidate: Profile, other: Profile) -> list[str]:
	reasons = []
	if candidate.emails & other.emails:
		reasons.append("same email")
	if any(is_same_phone(mine, theirs) for mine in candidate.phones for theirs in other.phones):
		reasons.append("same phone")
	return reasons


def compare_details(candidate: Profile, other: Profile) -> list[str]:
	reasons = []
	if candidate.birth_date and other.birth_date:
		reasons.append(
			"same birth date" if candidate.birth_date == other.birth_date else "different birth date"
		)
	if candidate.gender in GENDERS and other.gender in GENDERS and candidate.gender != other.gender:
		reasons.append("different gender")
	if candidate.suffix and other.suffix and candidate.suffix != other.suffix:
		reasons.append("different suffix")
	return reasons


def name_words(name: str | None) -> list[str]:
	"""*name* as words without case, accents or punctuation: "O'Brien-Núñez" is ["obrien", "nunez"]."""
	text = unicodedata.normalize("NFKD", cstr(name))
	text = "".join(char for char in text if not unicodedata.combining(char)).casefold()
	text = re.sub(r"['\u2019.]", "", text)
	return re.sub(r"[\W_]+", " ", text).split()


def name_key(name: str | None) -> str:
	"""*name* reduced to one comparable word: "Mary-Kate" and "mary kate" are both "marykate"."""
	return "".join(name_words(name))


def get_last_name_variants(last_name: str | None, previous_last_name: str | None = None) -> tuple[str, ...]:
	"""Last names worth looking up as typed (the database ignores case and accents): the whole name, the name
	without a suffix such as "Jr.", and each part of a double name."""
	variants: set[str] = set()
	for name in (last_name, previous_last_name):
		whole = cstr(name).strip()
		without_suffix = re.sub(r"[\s,]+(jr|sr|ii|iii|iv|v)\.?$", "", whole, flags=re.IGNORECASE)
		parts = [part for part in re.split(r"[\s-]+", without_suffix) if len(part) >= 3]
		variants.update((whole, without_suffix, *parts))
	return tuple(sorted(variants - {""}))


def get_nickname_group(name: str) -> frozenset[str]:
	"""*name* and the names that may stand for it: its nicknames, the names it is short for, and their other nicknames."""
	return get_nickname_groups().get(name, frozenset((name,)))


@cache
def get_nickname_groups() -> dict[str, frozenset[str]]:
	"""Each name in the shipped nickname list, mapped to its group (see `get_nickname_group`)."""
	with open(NICKNAMES_FILE) as file:
		data = json.load(file)
	nicknames: dict[str, set[str]] = {}
	for source in (data["names"], data["additions"]):
		for name, short_names in source.items():
			nicknames.setdefault(name_key(name), set()).update(name_key(short) for short in short_names)

	groups: dict[str, set[str]] = {}
	for name, short_names in nicknames.items():
		groups.setdefault(name, {name}).update(short_names)
		for short in short_names:
			groups.setdefault(short, {short}).update({name, *short_names})
	return {name: frozenset(group) for name, group in groups.items()}


def is_similar(name: str, other: str) -> bool:
	"""True when two names of three letters or more read as one name spelled two ways."""
	if min(len(name), len(other)) < 3:
		return False
	return difflib.SequenceMatcher(None, name, other).ratio() >= SIMILAR_NAME_RATIO


def is_initial_of(initial: str, name: str) -> bool:
	return len(initial) == 1 and name.startswith(initial)


def is_same_phone(digits: str, other: str) -> bool:
	"""True when two numbers share their last digits, ignoring a country code or a trunk 0 typed on one."""
	digits, other = digits.lstrip("0"), other.lstrip("0")
	shared = min(len(digits), len(other), PHONE_TAIL)
	return shared >= MIN_PHONE_DIGITS and digits[-shared:] == other[-shared:]


@frappe.whitelist()
def get_possible_matches(candidate: dict | str) -> list[dict]:
	"""For the warning on a new Person: people the user may read who may already be *candidate*.

	Only readable people are returned, and nothing about the others, not even that they exist.
	"""
	frappe.has_permission("Person", "create", throw=True)
	candidate = frappe.parse_json(candidate)
	if not isinstance(candidate, dict):
		frappe.throw(_("Send the new person's details as a set of fields."))

	matches = find_matches(get_clean_candidate(candidate), limit=MAX_CANDIDATES)
	if not matches:
		return []
	names = dict(
		frappe.get_list(
			"Person",
			filters={"name": ("in", [match.person for match in matches])},
			fields=["name", "full_name"],
			as_list=True,
		)
	)
	readable = [match for match in matches if match.person in names][:5]
	return [
		{
			"person": match.person,
			"full_name": names[match.person],
			"score": match.score,
			"reasons": match.reasons,
		}
		for match in readable
	]


def get_clean_candidate(values: dict) -> dict:
	"""The candidate fields of *values*, sent by a browser, as the types `find_matches` expects."""
	candidate = {fieldname: cstr(values.get(fieldname)) for fieldname in PERSON_FIELDS if fieldname != "name"}
	for fieldname in ("emails", "phones"):
		value = values.get(fieldname) or []
		candidate[fieldname] = [cstr(item) for item in (value if isinstance(value, list) else [value])]
	return candidate


def record_possible_duplicates(person: str, matches: list[Match]) -> list[str]:
	"""Open a Possible Duplicate for each of *matches* not yet paired with *person*, and return the new names.

	A pair someone marked Not a Duplicate stays closed.
	"""
	created = []
	for match in matches:
		pair = sorted((person, match.person))
		if is_paired(*pair):
			continue
		duplicate = frappe.get_doc(
			{
				"doctype": POSSIBLE_DUPLICATE,
				"person": pair[0],
				"other_person": pair[1],
				# A Data Import skips field defaults, and the import opens these pairs.
				"status": OPEN,
				"score": match.score,
				"reasons": "\n".join(match.reasons),
			}
		).insert(ignore_permissions=True)
		created.append(duplicate.name)
	return created


def is_paired(person: str, other_person: str) -> bool:
	"""True when the two people already have a Possible Duplicate, in either order and of any status."""
	return bool(get_pairs(person, other_person))


def resolve_merged(person: str) -> None:
	"""After a merge into *person*, close the pairs that now name it twice and drop pairs that repeat another."""
	seen = set()
	for pair in get_pairs(person):
		if pair.person == pair.other_person:
			frappe.db.set_value(POSSIBLE_DUPLICATE, pair.name, "status", MERGED)
			continue
		key = tuple(sorted((pair.person, pair.other_person)))
		if key in seen:
			frappe.delete_doc(
				POSSIBLE_DUPLICATE, pair.name, ignore_permissions=True, force=True, delete_permanently=True
			)
		seen.add(key)


def get_pairs(person: str, other_person: str | None = None) -> list[frappe._dict]:
	"""The Possible Duplicates naming *person*, or naming both people when *other_person* is given, oldest first."""
	# church-scope: finds pairs by the people in them, whatever church reads them
	Pair = frappe.qb.DocType(POSSIBLE_DUPLICATE)
	if other_person:
		condition = ((Pair.person == person) & (Pair.other_person == other_person)) | (
			(Pair.person == other_person) & (Pair.other_person == person)
		)
	else:
		condition = (Pair.person == person) | (Pair.other_person == person)
	return (
		frappe.qb.from_(Pair)
		.select(Pair.name, Pair.person, Pair.other_person)
		.where(condition)
		.orderby(Pair.creation)
		.run(as_dict=True)
	)


# Guest input is linked to an existing person only when the match shares one reason from each set.
SHARED_CONTACT = frozenset(("same email", "same phone"))
SAME_FIRST_NAME = frozenset(("same first name", "nickname of first name"))
SAME_LAST_NAME = frozenset(("same last name", "matches previous last name"))
# A guest never saw the member directory's choices, so the people guest input adds share nothing in it.
SHARES_NOTHING = dict.fromkeys(SHARE_DEFAULTS, 0)


def is_strong_match(match: Match) -> bool:
	"""True when the match shares the guest's email or phone, first name and last name.

	A nickname counts as the first name and a previous last name as the last name.
	"""
	reasons = set(match.reasons)
	return all(reasons & wanted for wanted in (SHARED_CONTACT, SAME_FIRST_NAME, SAME_LAST_NAME))


def find_or_add_person(candidate: dict, church: str | None, source: str) -> tuple[str, bool]:
	"""The one person who strongly matches what a guest typed, else a new Visitor: (person, added).

	*candidate* is read as `find_matches` reads it (first_name, last_name, emails, phones). A new Visitor gets
	the Person source *source*, and the other matches are left for staff as its possible duplicates. Guest input
	never changes an existing person.
	"""
	matches = find_matches(candidate, church=church)
	strong = [match for match in matches if is_strong_match(match)]
	if len(strong) == 1:
		return strong[0].person, False

	person = add_visitor(candidate, church, source)
	record_possible_duplicates(person, matches)
	return person, True


def add_visitor(candidate: dict, church: str | None, source: str) -> str:
	"""Add a Visitor from guest input. An email or phone another person holds is shared from them."""
	person = frappe.get_doc(
		{
			"doctype": "Person",
			"first_name": candidate.get("first_name"),
			"last_name": candidate.get("last_name"),
			"church": church,
			"membership": VISITOR,
			"source": source,
			**SHARES_NOTHING,
		}
	)
	for fieldname, child_doctype, value_field, values in (
		(EMAIL_FIELD, EMAIL_DOCTYPE, "email_address", candidate.get("emails") or []),
		(PHONE_FIELD, PHONE_DOCTYPE, "phone_number", candidate.get("phones") or []),
	):
		for value in values:
			person.append(
				fieldname,
				{
					value_field: value,
					"shared_from_type": person.doctype,
					"shared_from": get_other_holder(person, child_doctype, value_field, value),
				},
			)
	return person.insert(ignore_permissions=True).name
