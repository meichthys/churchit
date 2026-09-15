# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Birthdays and wedding anniversaries falling in a window of days, as a bulletin prints them."""

import frappe
from frappe.utils import formatdate, getdate

ACTIVE_MEMBER_STATUS = "Active"


def birthdays(start, end, members_only=True):
	"""People born on a day between *start* and *end* inclusive, as (day, name), earliest first."""
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")
	query = (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on((LifeEvent.parent == Person.name) & (LifeEvent.parenttype == "Person"))
		.select(Person.full_name, LifeEvent.date)
		.where((LifeEvent.event_type == "Birth") & LifeEvent.date.isnotnull())
	)
	if members_only:
		query = query.where(Person.membership_status == ACTIVE_MEMBER_STATUS)
	rows = [
		(occurrence, row.full_name)
		for row in query.run(as_dict=True)
		if (occurrence := occurrence_between(row.date, start, end))
	]
	return [frappe._dict(day=formatdate(day, "MMM d"), name=name) for day, name in sorted(rows)]


def anniversaries(start, end, members_only=True):
	"""Couples whose wedding anniversary falls between *start* and *end*, as (day, name), one row per couple."""
	filters = {"is_married": 1, "anniversary": ("is", "set")}
	if members_only:
		filters["membership_status"] = ACTIVE_MEMBER_STATUS
	people = frappe.get_all(
		"Person",
		filters=filters,
		fields=["name", "first_name", "last_name", "full_name", "spouse", "anniversary"],
	)
	rows = []
	listed = set()
	for person in people:
		occurrence = occurrence_between(person.anniversary, start, end)
		if not occurrence or person.name in listed:
			continue
		listed.update({person.name, person.spouse})
		rows.append((occurrence, couple_name(person)))
	return [frappe._dict(day=formatdate(day, "MMM d"), name=name) for day, name in sorted(rows)]


def occurrence_between(date, start, end):
	"""The date's month-and-day occurrence within the window, or None when it falls outside."""
	date, start, end = getdate(date), getdate(start), getdate(end)
	for year in range(start.year, end.year + 1):
		occurrence = yearly_occurrence(date, year)
		if start <= occurrence <= end:
			return occurrence
	return None


def yearly_occurrence(date, year):
	try:
		return date.replace(year=year)
	except ValueError:  # February 29 in a common year
		return date.replace(year=year, day=28)


def couple_name(person):
	"""``Matt & Sarah Smith`` when the spouses share a last name, otherwise both full names."""
	if not person.spouse:
		return person.full_name
	spouse = frappe.db.get_value(
		"Person", person.spouse, ["first_name", "last_name", "full_name"], as_dict=True
	)
	if not spouse:
		return person.full_name
	if spouse.last_name == person.last_name:
		return f"{person.first_name} & {spouse.first_name} {person.last_name}"
	return f"{person.full_name} & {spouse.full_name}"
