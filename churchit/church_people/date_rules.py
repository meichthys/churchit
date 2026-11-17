# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The dates a Person may hold: no birth, death or anniversary in the future, and dates in the right order.

Only a date that the save adds or changes is refused, so an older record with a bad date still saves its
other changes.
"""

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

from churchit.church_people.derived import BIRTH, DEATH

ONLY_ONCE = (BIRTH, DEATH)


def refuse_impossible_dates(person) -> None:
	"""Refuse a changed date that is in the future or out of order, and a second Birth or Death event."""
	before = person.get_doc_before_save()
	earlier = {row.name: row for row in (before.life_events if before else [])}
	events = [row for row in person.life_events or [] if row.event_type in ONLY_ONCE]
	# Unticking No Year changes the date too: a month and day picked in this year can lie ahead.
	changed = [
		row
		for row in events
		if is_new_or_changed(row, earlier.get(row.name), "date", "event_type", "year_unknown")
	]
	anniversary_changed = is_new_or_changed(person, before, "anniversary", "anniversary_year_unknown")

	refuse_second_events(person, events, before)
	refuse_future_dates(person, changed, anniversary_changed)
	refuse_dates_out_of_order(person, events, changed, anniversary_changed)
	refuse_positions_out_of_order(person, before)


def is_new_or_changed(row, earlier, *fieldnames) -> bool:
	return not earlier or any(cstr(row.get(name)) != cstr(earlier.get(name)) for name in fieldnames)


def refuse_second_events(person, events, before) -> None:
	for event_type in ONLY_ONCE:
		count = sum(row.event_type == event_type for row in events)
		earlier = sum(row.event_type == event_type for row in (before.life_events if before else []))
		if count > 1 and count > earlier:
			frappe.throw(_("A person can have only one {0} life event.").format(_(event_type)))


def refuse_future_dates(person, changed, anniversary_changed: bool) -> None:
	messages = {
		BIRTH: _("A birth date cannot be in the future."),
		DEATH: _("A death date cannot be in the future."),
	}
	for row in changed:
		if row.date and not row.year_unknown and getdate(row.date) > getdate(nowdate()):
			frappe.throw(messages[row.event_type])

	if (
		person.anniversary
		and not person.anniversary_year_unknown
		and anniversary_changed
		and getdate(person.anniversary) > getdate(nowdate())
	):
		frappe.throw(_("An anniversary cannot be in the future."))


def refuse_dates_out_of_order(person, events, changed, anniversary_changed: bool) -> None:
	birth = next(
		(row for row in events if row.event_type == BIRTH and row.date and not row.year_unknown), None
	)
	death = next((row for row in events if row.event_type == DEATH and row.date), None)

	if birth and death and (birth in changed or death in changed):
		if getdate(death.date) < getdate(birth.date):
			frappe.throw(_("A death date cannot be before the birth date."))

	if birth and person.anniversary and not person.anniversary_year_unknown:
		if (birth in changed or anniversary_changed) and getdate(person.anniversary) < getdate(birth.date):
			frappe.throw(_("An anniversary cannot be before the birth date."))


def refuse_positions_out_of_order(person, before) -> None:
	earlier = {row.name: row for row in (before.positions if before else [])}
	for row in person.positions or []:
		if not (row.start_date and row.end_date) or getdate(row.end_date) >= getdate(row.start_date):
			continue
		if is_new_or_changed(row, earlier.get(row.name), "start_date", "end_date"):
			frappe.throw(_("Row {0}: the End Date cannot be before the Start Date.").format(row.idx))
