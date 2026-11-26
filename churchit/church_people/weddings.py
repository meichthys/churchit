# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A marriage's Wedding life event, the one place a Person's anniversary is kept.

Each marriage has its own Wedding row, whose `spouse` names the other spouse. `derived` sets the read-only
anniversary from the row of the current marriage. A new marriage gets a row without a date (`start_wedding`),
so the office sees where the date goes, and a row from an earlier marriage never becomes the new one. An
anniversary typed anywhere but the desk form (the member portal, a returned card, an import, the API) goes onto
the current row (`record_typed_anniversary`), and a linked couple keeps their two rows the same
(`share_with_spouse`).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr

from churchit.church_people.derived import (
	WEDDING,
	get_current_wedding,
	get_marriage_years,
	get_next_anniversary,
)
from churchit.church_people.doctype.marital_status.marital_status import MARRIED, WIDOWED, WITH_SPOUSE
from churchit.church_scope import has_church_access, is_people_directory_private

# What a couple's two Wedding rows share besides the date and its No Year.
DETAIL_FIELDS = ("location", "officiant")


def start_wedding(person: Document) -> None:
	"""Give a new marriage of *person* its own Wedding row: a row added in this save, else one without a date.

	A row that names the spouse is the marriage's row already. A new marriage is a newly Married person, or a
	married person who links a different spouse. A spouse linked to someone Married to no one named is the same
	marriage, whose last row naming no one `share_with_spouse` names.
	"""
	if person.marital_status != MARRIED or get_named_row(person, person.spouse):
		return
	before = person.get_doc_before_save()
	stored = {row.name for row in before.life_events} if before else set()
	added = [row for row in get_weddings(person) if not row.spouse and row.name not in stored]
	if added:
		added[-1].spouse = person.spouse
	elif is_new_marriage(person, before):
		person.append("life_events", {"event_type": WEDDING, "spouse": person.spouse})


def is_new_marriage(person: Document, before: Document | None) -> bool:
	"""Whether *person*'s marriage is new: a new person, one who was Single, Divorced, Widowed or another status
	(a blank status is not known to be anything else), or one who links a spouse other than the one before."""
	if not before or before.marital_status not in (MARRIED, None, ""):
		return True
	return bool(before.spouse and person.spouse and before.spouse != person.spouse)


def is_married_to_no_one_else(person: Document, partner: str | None) -> bool:
	"""Whether stored *person* is linked to *partner*, or Married (or of unknown status) to no one named."""
	if partner and person.spouse == partner:
		return True
	return not person.spouse and person.marital_status in (MARRIED, None, "")


def refuse_marrying_a_late_spouse(person: Document) -> None:
	"""Refuse to make a Widowed *person* Married again to the spouse who has died, which would write a new
	anniversary over the first marriage's Wedding rows. A new marriage needs the new spouse."""
	before = person.get_doc_before_save()
	if not before or before.marital_status != WIDOWED or person.marital_status != MARRIED:
		return
	if not person.spouse or person.spouse != before.spouse:
		return
	late = frappe.db.get_value("Person", person.spouse, ["full_name", "is_deceased"], as_dict=True)
	if late and late.is_deceased:
		frappe.throw(
			_("{0} has died. To record a new marriage, choose the new spouse in Spouse.").format(
				frappe.bold(late.full_name)
			)
		)


def refuse_another_churches_partner(person: Document) -> None:
	"""In a private directory, refuse a Wedding row that the user points at a person of a church they cannot see.

	The rows that name the linked spouse are checked with the spouse, and the app's own saves skip the check.
	"""
	if person.flags.ignore_permissions or not is_people_directory_private():
		return
	before = person.get_doc_before_save()
	stored = {row.name: row.spouse for row in before.life_events} if before else {}
	for row in get_weddings(person):
		if not row.spouse or row.spouse in (person.spouse, stored.get(row.name)):
			continue
		partner = frappe.db.get_value("Person", row.spouse, ["full_name", "church"], as_dict=True)
		if partner and not has_church_access(frappe.session.user, partner.church):
			frappe.throw(
				_("Row {0}: {1} belongs to another church, so you cannot name them as a spouse.").format(
					row.idx, frappe.bold(partner.full_name)
				),
				frappe.PermissionError,
			)


def record_typed_anniversary(person: Document) -> None:
	"""Put an anniversary or No Year that this save changes on *person*'s current Wedding row, adding one.

	Only a married, widowed or blank status has an anniversary, so another status's rows stay as they are.
	"""
	if not has_typed_anniversary(person) or person.marital_status not in (*WITH_SPOUSE, None, ""):
		return
	date = person.anniversary or None
	year_unknown = cint(person.anniversary_year_unknown) if date else 0
	wedding = get_current_wedding(person.life_events, person.spouse)
	if wedding and (cstr(wedding.date), cint(wedding.year_unknown)) == (cstr(date), year_unknown):
		return
	if not wedding and not date:
		return
	wedding = wedding or person.append("life_events", {"event_type": WEDDING, "spouse": person.spouse})
	wedding.update({"date": date, "year_unknown": year_unknown})


def has_typed_anniversary(person: Document) -> bool:
	"""Whether this save changes the anniversary or its No Year. A web form sends an empty value for a blank one."""
	before = person.get_doc_before_save()
	if not before:
		return bool(person.anniversary)
	return cstr(person.anniversary) != cstr(before.anniversary) or cint(
		person.anniversary_year_unknown
	) != cint(before.anniversary_year_unknown)


def forget_spouse(person: str) -> None:
	"""Name no one on the Wedding rows that name *person*, who is deleted or anonymized; the marriages stay."""
	frappe.db.set_value("Life Event", {"spouse": person, "parenttype": "Person"}, "spouse", None)


def share_with_spouse(person: Document, spouse: Document) -> dict:
	"""Make *person*'s and *spouse*'s rows for their wedding the same, each naming the other spouse.

	*spouse* is the spouse as stored. A field keeps *person*'s value unless it is blank and this save did not
	clear it; then it takes *spouse*'s. Returns the anniversary values for the caller to write on *spouse* when
	their row or their anniversary changes, so a form that *spouse* has open cannot save the old row back.
	"""
	own = get_current_wedding(person.life_events, spouse.name)
	theirs = get_spouse_row(spouse, person.name)
	if not (own or theirs):
		return {}
	own = own or person.append("life_events", {"event_type": WEDDING})
	if theirs:
		take_blanks(person, own, theirs)
	own.spouse = spouse.name
	values = {
		"date": own.date,
		"year_unknown": cint(own.year_unknown),
		**{field: own.get(field) for field in DETAIL_FIELDS},
		"spouse": person.name,
	}
	is_changed = write_spouse_row(spouse, theirs, values)
	anniversary = get_spouse_anniversary(own, spouse)
	if is_changed or (cstr(spouse.anniversary), cint(spouse.anniversary_year_unknown)) != (
		cstr(anniversary["anniversary"]),
		anniversary["anniversary_year_unknown"],
	):
		return anniversary
	return {}


def get_spouse_row(spouse: Document, partner: str):
	"""*spouse*'s Wedding row for their marriage to *partner*: the row naming them, else, when *spouse* was
	already linked to *partner* or Married to no one named, their last row naming no one; or None."""
	named = get_named_row(spouse, partner)
	if named or not is_married_to_no_one_else(spouse, partner):
		return named
	return next((row for row in reversed(get_weddings(spouse)) if not row.spouse), None)


def take_blanks(person: Document, own, theirs) -> None:
	"""Fill each field that *own* lacks from *theirs*, unless this save cleared it. The No Year goes with the date."""
	before = person.get_doc_before_save()
	stored = next((row for row in (before.life_events if before else []) if row.name == own.name), None)

	def is_cleared(field: str) -> bool:
		return bool(stored and stored.get(field) and not own.get(field))

	if not own.date and not is_cleared("date"):
		own.update({"date": theirs.date, "year_unknown": theirs.year_unknown})
	for field in DETAIL_FIELDS:
		if not own.get(field) and not is_cleared(field):
			own.set(field, theirs.get(field))


def write_spouse_row(spouse: Document, theirs, values: dict) -> bool:
	"""Write *values* on *spouse*'s Wedding row *theirs*, or add the row. Returns whether anything changed."""
	if not theirs:
		frappe.get_doc(
			{
				"doctype": "Life Event",
				"parent": spouse.name,
				"parenttype": "Person",
				"parentfield": "life_events",
				"idx": len(spouse.life_events) + 1,
				"event_type": WEDDING,
				**values,
			}
		).db_insert()
		return True
	if all(cstr(theirs.get(field)) == cstr(value) for field, value in values.items()):
		return False
	frappe.db.set_value("Life Event", theirs.name, values, update_modified=False)
	return True


def get_spouse_anniversary(wedding, spouse: Document) -> dict:
	"""The anniversary fields that *spouse* takes from the couple's *wedding* row."""
	year_unknown = cint(wedding.year_unknown) if wedding.date else 0
	return {
		"anniversary": wedding.date,
		"anniversary_year_unknown": year_unknown,
		"marriage_years": get_marriage_years(wedding.date, year_unknown),
		"next_anniversary": get_next_anniversary(wedding.date, spouse.is_deceased),
	}


def get_weddings(person: Document) -> list:
	return [row for row in person.life_events if row.event_type == WEDDING]


def get_named_row(person: Document, partner: str | None):
	"""*person*'s Wedding row that names *partner*, or None."""
	return next((row for row in get_weddings(person) if partner and row.spouse == partner), None)
