# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who may check in to a Function, and when: age and grade bounds, room capacity and the self check-in window."""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_people.derived import (
	FINAL_GRADE,
	KINDERGARTEN,
	get_grade,
	get_grade_number,
	years_between,
)

# The Function grade bounds, at the index of their grade number.
GRADES = [KINDERGARTEN, *(f"Grade {grade}" for grade in range(1, FINAL_GRADE + 1))]
BLOCK = "Block"
WARN = "Warn"


class RoomFullError(frappe.ValidationError):
	pass


def get_bound_problem(function: str, person: str) -> str | None:
	"""Why *person* is outside *function*'s age or grade bounds on its start date, or None.

	An unknown age or grade does not pass a set bound.
	"""
	bounds = frappe.db.get_value(
		"Function", function, ["start_date", "min_age", "max_age", "min_grade", "max_grade"], as_dict=True
	)
	person = frappe.db.get_value("Person", person, ["birth_date", "graduation_year"], as_dict=True)
	return get_age_problem(bounds, person) or get_grade_problem(bounds, person)


def get_capacity(function: str, for_update: bool = False) -> tuple[int, int]:
	"""(present, capacity) of *function*; a capacity of 0 means no limit.

	Present counts the check-ins not collected yet, Volunteers left out. Capacity sums the rooms of the
	Approved Room Bookings. *for_update* locks the counted rows, so a count under the Function row lock
	sees what another station committed: a plain read answers from the request's older snapshot. It takes
	the code lock first, the order get_security_code locks check-ins in, so two stations cannot deadlock.
	"""
	from churchit.church_ministries.doctype.function_check_in.function_check_in import (
		VOLUNTEER,  # function_check_in imports this module
	)

	# church-scope: Church Check-In has no Room Booking permission, and a Function's bookings follow it
	rooms = frappe.get_all("Room Booking", filters={"function": function, "status": "Approved"}, pluck="room")
	# church-scope: the booked rooms, which may be another church's shared rooms
	capacity = sum(frappe.get_all("Room", filters={"name": ("in", rooms)}, pluck="capacity")) if rooms else 0
	for_update = for_update and bool(capacity)
	if for_update:
		frappe.db.get_single_value("Check-In Settings", "security_codes", for_update=True)
	# church-scope: the check-ins of one Function, counted and never shown
	present = frappe.db.get_values(
		"Function Check-In",
		{"function": function, "collected_at": ("is", "not set"), "check_in_kind": ("!=", VOLUNTEER)},
		"name",
		for_update=for_update,
	)
	return len(present), capacity


def is_check_in_open(function: str) -> bool:
	"""Whether self check-in to *function* is open now: its time window, opened check_in_opens_minutes early."""
	fields = ["start_date", "end_date", "start_time", "end_time", "all_day"]
	start, end = get_time_window(frappe.db.get_value("Function", function, fields, as_dict=True))
	opens = cint(frappe.get_cached_doc("Check-In Settings").check_in_opens_minutes)
	return start - timedelta(minutes=opens) <= now_datetime() <= end


def get_age_problem(bounds, person) -> str | None:
	if not (bounds.min_age or bounds.max_age):
		return None
	if not person.birth_date:
		return _("No birth date, and this function has an age limit.")

	age = years_between(person.birth_date, bounds.start_date)
	if bounds.min_age and age < bounds.min_age:
		return _("Age {0}, under the youngest age of {1}.").format(age, bounds.min_age)
	if bounds.max_age and age > bounds.max_age:
		return _("Age {0}, over the oldest age of {1}.").format(age, bounds.max_age)
	return None


def get_grade_problem(bounds, person) -> str | None:
	if not (bounds.min_grade or bounds.max_grade):
		return None
	grade = get_grade_number(person.graduation_year, bounds.start_date)
	if grade is None:
		return _("No graduation year, and this function has a grade limit.")

	label = get_grade(person.graduation_year, bounds.start_date) or _("Not in school yet")
	if bounds.min_grade and grade < GRADES.index(bounds.min_grade):
		return _("{0}, below the lowest grade of {1}.").format(label, bounds.min_grade)
	if bounds.max_grade and grade > GRADES.index(bounds.max_grade):
		return _("{0}, above the highest grade of {1}.").format(label, bounds.max_grade)
	return None


@frappe.whitelist()
def get_bound_problems(function: str, persons: str | list[str]) -> dict[str, dict]:
	"""{person: {full_name, problem}} for the *persons* outside *function*'s bounds, so the station asks first."""
	from churchit.church_ministries.doctype.function_check_in.function_check_in import (
		is_shared_function,  # function_check_in imports this module
	)

	frappe.has_permission("Function Check-In", "create", throw=True)
	frappe.has_permission("Function", doc=function, throw=True)
	persons = frappe.parse_json(persons)
	# The same rule as check_in_persons: a shared function takes any church's people.
	if not is_shared_function(function):
		for person in persons:
			frappe.has_permission("Person", doc=person, throw=True)

	problems = {person: get_bound_problem(function, person) for person in persons}
	return {
		person: {"full_name": frappe.db.get_value("Person", person, "full_name"), "problem": problem}
		for person, problem in problems.items()
		if problem
	}


def refuse_a_full_room(function: str, adding: int) -> None:
	"""In Block mode, refuse *adding* people when *function*'s rooms cannot hold them. Call it under the Function row lock."""
	if not adding or frappe.get_cached_doc("Check-In Settings").capacity_mode != BLOCK:
		return
	present, capacity = get_capacity(function, for_update=True)
	if capacity and present + adding > capacity:
		frappe.throw(
			_("The room is full: {0} of {1} places are taken.").format(present, capacity),
			RoomFullError,
			title=_("Room Full"),
		)


def get_capacity_warning(function: str) -> str | None:
	"""In Warn mode, the warning a station shows when *function*'s rooms hold more people than they fit."""
	if frappe.get_cached_doc("Check-In Settings").capacity_mode != WARN:
		return None
	present, capacity = get_capacity(function)
	if capacity and present > capacity:
		return _("The room is over capacity: {0} people for {1} places.").format(present, capacity)
	return None


@frappe.whitelist()
def get_rooms(function: str) -> list[str]:
	"""The rooms of *function*'s Approved Room Bookings, which the station shows above its roster."""
	frappe.has_permission("Function", doc=function, throw=True)
	# church-scope: Church Check-In has no Room Booking permission, and a Function's bookings follow it
	rooms = frappe.get_all("Room Booking", filters={"function": function, "status": "Approved"}, pluck="room")
	# church-scope: the booked rooms, which may be another church's shared rooms
	return sorted(frappe.get_all("Room", filters={"name": ("in", rooms)}, pluck="room_name")) if rooms else []
