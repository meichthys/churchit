# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churches and people who keep their records away from churchit's own AI features.

A church that ticks Church.keep_away_from_ai and a person who ticks Person.exclude_from_ai (a member
does it on the Personal Details page) are left out of Brief Me, Draft Note, Explain, Draft with AI,
the study helpers, action items and suggestions on new requests. A person of such a church is left
out too, and so is a record of such a church or about such a person. The desk hides churchit's AI
buttons from a user whose churches all keep away (switch.extend_bootinfo). Flow chats, the Church
Office agent and AI apps that connect over MCP work with each user's own permissions and are not
limited (D5).

The flags are read with frappe.db and not as the caller, because what churchit's AI may send must not
depend on what the caller may read.
"""

from collections import defaultdict
from collections.abc import Iterable

import frappe
from frappe import _

from churchit.church_people.privacy import PERSONAL_DOCTYPES, RECORDS_ABOUT_THE_PERSON
from churchit.church_scope import SHARED_BY_FIELD, allowed_churches, is_multi_church, is_scoped, root_church

CHURCH_FIELD = "keep_away_from_ai"
PERSON_FIELD = "exclude_from_ai"
REFUSAL = (
	"Churchit's AI features leave this record out, because its church or the person it is about asked "
	"for that."
)
CHURCH_REFUSAL = "Your church keeps its records away from churchit's AI features."


def is_kept_away(doctype: str, name: str) -> bool:
	"""True when churchit's own AI features leave the record out: its church keeps away from AI, or it
	is or is about a person who keeps their details out of AI or whose church keeps away."""
	return name in get_kept_away(doctype, [name])


def refuse_kept_away(doctype: str, name: str) -> None:
	"""Refuse with one plain sentence when churchit's own AI features leave the record out."""
	if is_kept_away(doctype, name):
		frappe.throw(_(REFUSAL), frappe.PermissionError, title=_("Kept Away From AI"))


def refuse_kept_away_church(church: str | None) -> None:
	"""Refuse a new record of *church* when it keeps away; with no church, when every church the user
	may see keeps away."""
	if church in get_kept_away_churches() if church else is_user_kept_away():
		frappe.throw(_(CHURCH_REFUSAL), frappe.PermissionError, title=_("Kept Away From AI"))


def get_kept_away_records(records: Iterable[tuple[str, str]]) -> set[tuple[str, str]]:
	"""Those of *records*, (doctype, name) pairs, that churchit's own AI features leave out."""
	names = defaultdict(set)
	for doctype, name in records:
		names[doctype].add(name)
	return {(doctype, name) for doctype, each in names.items() for name in get_kept_away(doctype, each)}


def get_kept_away(doctype: str, names: Iterable[str]) -> set[str]:
	"""Those of *names*, records of *doctype*, that churchit's own AI features leave out (is_kept_away).

	A record is about a person through the field that churchit.church_people.privacy names for it, or
	a Dynamic Link to a Person (a prayer request's recipient).
	"""
	names = set(filter(None, names))
	if not names:
		return set()
	churches = get_kept_away_churches()
	if doctype == "Church":
		return names & churches

	meta = frappe.get_meta(doctype)
	person_fields = get_person_fields(meta)
	fields = get_deciding_fields(meta, person_fields)
	if not fields:
		return set()

	rows = frappe.db.get_values(doctype, {"name": ("in", list(names))}, ["name", *fields], as_dict=True)
	people = {row.name: get_people(row, person_fields) for row in rows}
	kept_people = get_kept_away("Person", {person for each in people.values() for person in each})
	only_church = None if is_multi_church() else root_church()
	return {
		row.name
		for row in rows
		if row.get(PERSON_FIELD)
		or get_church(row, meta, only_church) in churches
		or people[row.name] & kept_people
	}


def get_kept_away_churches() -> set[str]:
	"""The churches that keep their records away from churchit's own AI features."""
	if not frappe.get_meta("Church").has_field(CHURCH_FIELD):  # migrate adds it
		return set()
	return set(frappe.db.get_values("Church", {CHURCH_FIELD: 1}, "name", pluck=True))


def is_user_kept_away(user: str | None = None) -> bool:
	"""True when every church *user* may see keeps away from churchit's AI, so the desk hides its buttons."""
	churches = get_kept_away_churches()
	if not churches:
		return False
	readable = allowed_churches(user)
	if readable is None:
		readable = frappe.db.get_values("Church", {}, "name", pluck=True)
	return set(readable) <= churches


def get_deciding_fields(meta, person_fields: list[tuple[str, str | None]]) -> list[str]:
	"""The fields of a record of *meta* that decide whether it keeps away: its church, the people it is
	about and, on a Person, their own choice."""
	fields = [field for field in ("church", SHARED_BY_FIELD) if is_scoped(meta) and meta.has_field(field)]
	fields += [field for pair in person_fields for field in pair if field]
	if meta.name == "Person" and meta.has_field(PERSON_FIELD):  # migrate adds it
		fields.append(PERSON_FIELD)
	return fields


def get_person_fields(meta) -> list[tuple[str, str | None]]:
	"""(field, type field) of each field naming the person a record of *meta* is about; the type field
	is that of a Dynamic Link, which names a person only when it holds Person."""
	if meta.name == "Person":
		return []
	about = (*PERSONAL_DOCTYPES, *RECORDS_ABOUT_THE_PERSON)
	listed = [(field, None) for doctype, field in about if doctype == meta.name]
	return listed + [(df.fieldname, df.options) for df in meta.fields if df.fieldtype == "Dynamic Link"]


def get_people(row: dict, person_fields: list[tuple[str, str | None]]) -> set[str]:
	"""The people *row* is about, from *person_fields*."""
	return {
		row[field]
		for field, type_field in person_fields
		if row.get(field) and (not type_field or row.get(type_field) == "Person")
	}


def get_church(row: dict, meta, only_church: str | None) -> str | None:
	"""The church of a record: its own, the one that shared it, or *only_church*, a single-church site's."""
	if not is_scoped(meta):
		return None
	return row.get("church") or row.get(SHARED_BY_FIELD) or only_church
