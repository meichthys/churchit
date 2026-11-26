# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import cint, cstr

from churchit.church_people.derived import (
	WEDDING,
	get_anniversary_values,
	get_marriage_years,
	get_next_anniversary,
)
from churchit.church_people.doctype.marital_status.marital_status import MARRIED

# The life event type that repeated the Anniversary field, which new sites no longer get.
ANNIVERSARY_TYPE = "Anniversary"


def execute():
	"""Keep each anniversary on a Wedding life event, which the anniversary now comes from.

	Anniversary life events, and the follow-up triggers on them, become Wedding ones, and the Anniversary type
	goes. A person whose anniversary has no Wedding row with its date gets one, naming the spouse, as the last
	row, so the anniversary stays as it is. A married person without an anniversary gets a Wedding row without a
	date, as a new marriage does. Then every person with a Wedding row takes the anniversary from it.
	"""
	if not frappe.db.exists("Life Event Type", WEDDING):
		frappe.get_doc({"doctype": "Life Event Type", "type": WEDDING}).insert(ignore_permissions=True)
	retire_anniversary_type()

	for person in frappe.get_all(
		"Person",
		or_filters={"anniversary": ("is", "set"), "marital_status": MARRIED},
		fields=["name", "spouse", "anniversary", "anniversary_year_unknown"],
	):
		place_wedding(person, [row for row in get_rows(person.name) if row.event_type == WEDDING])
	for name in frappe.get_all(
		"Life Event", filters={"parenttype": "Person", "event_type": WEDDING}, pluck="parent", distinct=True
	):
		set_anniversary(name)


def retire_anniversary_type() -> None:
	"""Turn Anniversary life events and the follow-up triggers on them into Wedding ones, and delete the type.

	A record of another kind that still links the type keeps it, rather than stop the upgrade.
	"""
	life_event = frappe.qb.DocType("Life Event")
	frappe.qb.update(life_event).set(life_event.event_type, WEDDING).where(
		life_event.event_type == ANNIVERSARY_TYPE
	).run()
	trigger = frappe.qb.DocType("Follow-up Trigger")
	frappe.qb.update(trigger).set(trigger.value, WEDDING).where(
		(trigger.value_type == "Life Event Type") & (trigger.value == ANNIVERSARY_TYPE)
	).run()
	try:
		frappe.delete_doc_if_exists("Life Event Type", ANNIVERSARY_TYPE)
	except frappe.LinkExistsError:
		pass


def place_wedding(person, weddings: list) -> None:
	"""Name the spouse on the row of *person*'s marriage, adding the row when there is none.

	With an anniversary, the row is one with its date, moved last, so it stays the row that the anniversary comes
	from when it names no one. Without one, it is the row naming the spouse, else the last row naming no one.
	"""
	if person.anniversary:
		row = next(
			(
				row
				for row in weddings
				if cstr(row.date) == cstr(person.anniversary) and row.spouse in (None, "", person.spouse)
			),
			None,
		)
	else:
		named = next((row for row in weddings if person.spouse and row.spouse == person.spouse), None)
		row = named or next((row for row in reversed(weddings) if not row.spouse), None)
	last = max((row.idx for row in get_rows(person.name)), default=0)
	if row:
		values = {"spouse": person.spouse}
		if person.anniversary and row.idx != last:
			values["idx"] = last + 1
		frappe.db.set_value("Life Event", row.name, values, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Life Event",
			"parent": person.name,
			"parenttype": "Person",
			"parentfield": "life_events",
			"idx": last + 1,
			"event_type": WEDDING,
			"date": person.anniversary,
			"year_unknown": cint(person.anniversary_year_unknown) if person.anniversary else 0,
			"spouse": person.spouse,
		}
	).db_insert()


def set_anniversary(name: str) -> None:
	person = frappe.db.get_value(
		"Person",
		name,
		["marital_status", "spouse", "is_deceased", "anniversary", "anniversary_year_unknown"],
		as_dict=True,
	)
	if not person:
		return
	values = get_anniversary_values(get_rows(name), person.marital_status, person.spouse)
	if (cstr(person.anniversary), cint(person.anniversary_year_unknown)) == (
		cstr(values["anniversary"]),
		values["anniversary_year_unknown"],
	):
		return
	values["marriage_years"] = get_marriage_years(values["anniversary"], values["anniversary_year_unknown"])
	values["next_anniversary"] = get_next_anniversary(values["anniversary"], person.is_deceased)
	frappe.db.set_value("Person", name, values, update_modified=False)


def get_rows(name: str) -> list:
	return frappe.get_all(
		"Life Event",
		filters={"parent": name, "parenttype": "Person"},
		fields=["name", "idx", "event_type", "date", "year_unknown", "spouse"],
		order_by="idx asc",
	)
