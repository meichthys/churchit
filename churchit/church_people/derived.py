# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Person fields worked out from other fields, never typed in.

`sync_derived` sets them on every save. `refresh_daily` brings every person up to date between saves.
"""

import calendar

import frappe
from dateutil.relativedelta import relativedelta
from frappe.utils import getdate, nowdate

from churchit.church_people import household

ADULT = "Adult"
CHILD = "Child"
BIRTH = "Birth"
DEATH = "Death"
DERIVED_FIELDS = (
	"birth_date",
	"birth_month",
	"birth_day",
	"is_deceased",
	"deceased_date",
	"age",
	"life_stage",
)
KINDERGARTEN = "Kindergarten"
GRADUATED = "Graduated"
FINAL_GRADE = 12


def years_between(start, end) -> int:
	"""Whole years from *start* to *end*, never below 0."""
	return max(relativedelta(getdate(end), getdate(start)).years, 0)


def years_since(date):
	"""Whole years from ``date`` until today; 0 when ``date`` is empty."""
	if not date:
		return 0
	return years_between(date, nowdate())


def sync_derived(person) -> None:
	"""Set *person*'s fields that come from their life events, household role, anniversary and graduation year."""
	# A new or changed family has no roster row for this person until on_update adds it.
	role = None if person.has_value_changed("family") else household.role_of(person.name)
	person.update(get_derived_values(person.life_events or [], role))
	person.marriage_years = years_since(person.anniversary)
	person.grade = get_grade(person.graduation_year)


def get_derived_values(life_events, role) -> dict:
	"""Birth, death, age and life stage from a person's *life_events* rows and household *role*, as stored.

	The first dated Birth row is the birth. Its month and day always count, its year only when it is known.
	An unknown age is 0, like a baby's, so `birth_date` and the death fields tell whether the age is known.
	"""
	birth = next((row for row in life_events if row.event_type == BIRTH and row.date), None)
	deaths = [row for row in life_events if row.event_type == DEATH]
	deceased_date = next((row.date for row in deaths if row.date), None)
	birth_date = birth.date if birth and not birth.year_unknown else None
	age = get_age(birth_date, bool(deaths), deceased_date)
	return {
		"birth_date": birth_date,
		"birth_month": getdate(birth.date).month if birth else 0,
		"birth_day": getdate(birth.date).day if birth else 0,
		"is_deceased": int(bool(deaths)),
		"deceased_date": deceased_date,
		"age": age or 0,
		"life_stage": life_stage_for(role, age),
	}


def has_known_age(Person):
	"""Query criterion for the people whose stored age is real, on the Person table *Person*.

	It is the rule `get_age` follows: the birth year is known, and so is the date of death of anyone who died.
	"""
	return Person.birth_date.isnotnull() & ((Person.is_deceased == 0) | Person.deceased_date.isnotnull())


def get_age(birth_date, is_deceased: bool, deceased_date) -> int | None:
	"""Whole years from *birth_date* to today, or to the death; None when either end is unknown."""
	if not birth_date or (is_deceased and not deceased_date):
		return None
	return years_between(birth_date, deceased_date or nowdate())


def life_stage_for(role, age):
	"""Adult or Child from a household *role*, else from *age* against People Settings' adult age; None when neither is known."""
	if role:
		return CHILD if role == CHILD else ADULT
	if age is None:
		return None
	return ADULT if age >= frappe.db.get_single_value("People Settings", "adult_age") else CHILD


def get_grade_number(graduation_year: int | None, on_date=None) -> int | None:
	"""The school grade number on *on_date* (today by default) of someone who finishes high school in *graduation_year*.

	0 is kindergarten, below 0 is before it and above FINAL_GRADE is after graduation; None without a year. The
	grade moves up on the first day of People Settings' school year start month.
	"""
	if not graduation_year:
		return None
	return FINAL_GRADE - (graduation_year - get_school_year_end(getdate(on_date)))


def get_grade(graduation_year: int | None, on_date=None) -> str | None:
	"""The school grade on *on_date*: Kindergarten, Grade 1 to Grade 12, then Graduated; None before kindergarten or without a year."""
	grade = get_grade_number(graduation_year, on_date)
	if grade is None or grade < 0:
		return None
	if grade > FINAL_GRADE:
		return GRADUATED
	return f"Grade {grade}" if grade else KINDERGARTEN


def get_school_year_end(on_date) -> int:
	"""The year in which the school year holding *on_date* ends.

	A school year that starts in January ends in the same year; any other ends in the next year.
	"""
	start_month = list(calendar.month_name).index(
		frappe.db.get_single_value("People Settings", "school_year_start_month")
	)
	start_year = on_date.year if on_date.month >= start_month else on_date.year - 1
	return start_year + 1 if start_month > 1 else start_year


def refresh_daily():
	"""Daily scheduler, and the backfill for a newly derived field: bring every person's derived fields up to date.

	It compares every person rather than only today's birthdays, so a day the scheduler missed is caught up.
	"""
	life_events = get_birth_and_death_events()
	# church-scope: scheduled daily job: recomputes stored figures, shows nobody anything
	people = frappe.get_all(
		"Person",
		fields=[
			"name",
			"family",
			"anniversary",
			"marriage_years",
			"graduation_year",
			"grade",
			*DERIVED_FIELDS,
		],
	)
	for person in people:
		role = household.role_of(person.name) if person.family else None
		current = get_derived_values(life_events.get(person.name, []), role)
		current["marriage_years"] = years_since(person.anniversary)
		current["grade"] = get_grade(person.graduation_year)
		changed = {
			field: value for field, value in current.items() if (person[field] or None) != (value or None)
		}
		if changed:
			frappe.db.set_value("Person", person.name, changed, update_modified=False)


def get_birth_and_death_events() -> dict[str, list]:
	"""Every person's Birth and Death rows in table order, by person."""
	rows = frappe.get_all(
		"Life Event",
		filters={"parenttype": "Person", "event_type": ("in", (BIRTH, DEATH))},
		fields=["parent", "event_type", "date", "year_unknown"],
		order_by="parent asc, idx asc",
	)
	by_person = {}
	for row in rows:
		by_person.setdefault(row.parent, []).append(row)
	return by_person
