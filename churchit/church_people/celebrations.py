# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Birthdays and wedding anniversaries falling in a window of days, as a bulletin prints them.

People who ticked Hide from Directory and Bulletin are left out, and so is a couple's anniversary when either is.
The same goes for people who have died.
"""

from datetime import date

import frappe
from frappe.utils import formatdate, getdate

from churchit.church_people.doctype.marital_status.marital_status import MARRIED
from churchit.church_people.membership import is_active_member, living_people_filter


def birthdays(start, end, members_only=True, church=None):
	"""People born on a day between *start* and *end* inclusive, as (day, name), earliest first."""
	# church-scope: scoped by the church the caller passes in
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(Person.full_name, Person.birth_month, Person.birth_day, Person.birth_date)
		.where(Person.birth_month > 0)
		.where((Person.hide_from_directory == 0) & living_people_filter(Person))
	)
	if members_only:
		query = query.where(is_active_member(Person))
	if church:
		query = query.where(Person.church == church)
	return [
		frappe._dict(day=formatdate(row.birthday, "MMM d"), name=row.full_name)
		for row in get_birthday_rows(query.run(as_dict=True), start, end)
	]


def get_birthday_rows(people, start, end):
	"""Those of *people* with a birthday between *start* and *end*, by day then name.

	Each row gains its `birthday` in the window and the `age` it turns then, None when the birth year is
	unknown. A person row needs full_name, birth_month, birth_day and birth_date.
	"""
	rows = []
	for person in people:
		birthday = occurrence_between(person.birth_month, person.birth_day, start, end)
		if birthday:
			turning = birthday.year - person.birth_date.year if person.birth_date else None
			rows.append(frappe._dict(person, birthday=birthday, age=turning))
	return sorted(rows, key=lambda row: (row.birthday, row.full_name))


def anniversaries(start, end, members_only=True, church=None):
	"""Couples whose wedding anniversary falls between *start* and *end*, as (day, name), one row per couple."""
	# church-scope: scoped by the church the caller passes in
	Person = frappe.qb.DocType("Person")
	Spouse = frappe.qb.DocType("Person").as_("spouse")
	query = (
		frappe.qb.from_(Person)
		.left_join(Spouse)
		.on(Spouse.name == Person.spouse)
		.select(
			Person.name,
			Person.first_name,
			Person.last_name,
			Person.full_name,
			Person.spouse,
			Person.anniversary,
		)
		.where((Person.marital_status == MARRIED) & Person.anniversary.isnotnull())
		.where((Person.hide_from_directory == 0) & living_people_filter(Person))
		.where(Spouse.name.isnull() | ((Spouse.hide_from_directory == 0) & living_people_filter(Spouse)))
	)
	if members_only:
		query = query.where(is_active_member(Person))
	if church:
		query = query.where(Person.church == church)
	rows = []
	listed = set()
	for person in query.run(as_dict=True):
		anniversary = getdate(person.anniversary)
		occurrence = occurrence_between(anniversary.month, anniversary.day, start, end)
		if not occurrence or person.name in listed:
			continue
		listed.update({person.name, person.spouse})
		rows.append((occurrence, couple_name(person)))
	return [frappe._dict(day=formatdate(day, "MMM d"), name=name) for day, name in sorted(rows)]


def occurrence_between(month, day, start, end):
	"""The date that *month* and *day* fall on between *start* and *end*, or None when they fall outside."""
	start, end = getdate(start), getdate(end)
	for year in range(start.year, end.year + 1):
		occurrence = yearly_occurrence(month, day, year)
		if start <= occurrence <= end:
			return occurrence
	return None


def yearly_occurrence(month, day, year):
	try:
		return date(year, month, day)
	except ValueError:  # February 29 in a common year
		return date(year, month, 28)


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
