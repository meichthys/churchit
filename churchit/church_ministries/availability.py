# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Who can serve on a ministry team when: blocks, double booking, checks and monthly limits.

A Ministry Team Assignment shows these problems as warnings and never refuses because of them.
Code that picks people itself, such as auto-fill, takes only people `is_available` passes.
"""

from datetime import date, datetime, time

import frappe
from dateutil.relativedelta import relativedelta
from dateutil.rrule import MONTHLY, WEEKLY, rrule, weekday
from frappe import _
from frappe.query_builder.functions import Coalesce, Count
from frappe.utils import format_date, getdate

from churchit.church_ministries.doctype.function.function import get_time_window
from churchit.church_ministries.doctype.ministry_team_assignment import (
	ministry_team_assignment as team_assignment,
)
from churchit.church_people.doctype.background_check import background_check

# Each repeat of a block: its rrule frequency and interval, and the most days one block may last.
REPEATS = {
	"Weekly": (WEEKLY, 1, 7),
	"Every Other Week": (WEEKLY, 2, 14),
	"Monthly on the Same Weekday": (MONTHLY, 1, 28),
}


def get_blocks_covering(person: str, from_date, to_date) -> list[frappe._dict]:
	"""Blocks that keep *person* from serving on any day from *from_date* to *to_date*.

	A block of someone in the same family counts when it covers the whole household. Each block
	carries covered_from and covered_to, the dates of its first repeat in that range.
	"""
	from_date, to_date = getdate(from_date), getdate(to_date)
	Block = frappe.qb.DocType("Ministry Team Block")
	covers_person = Block.person == person
	family = frappe.db.get_value("Person", person, "family")
	if family:
		household = frappe.get_all("Person", filters={"family": family}, pluck="name")
		covers_person = covers_person | (Block.person.isin(household) & (Block.whole_household == 1))

	still_repeats = (Coalesce(Block.repeat_frequency, "") != "") & (
		Block.repeat_until.isnull() | (Block.repeat_until >= from_date)
	)
	# church-scope: blocks on the one person being scheduled, wherever their church is
	blocks = (
		frappe.qb.from_(Block)
		.select(
			Block.name,
			Block.person,
			Block.from_date,
			Block.to_date,
			Block.reason,
			Block.repeat_frequency,
			Block.repeat_until,
		)
		.where(covers_person & (Block.from_date <= to_date) & ((Block.to_date >= from_date) | still_repeats))
		.orderby(Block.from_date)
		.run(as_dict=True)
	)
	covering = []
	for block in blocks:
		dates = get_covered_dates(block, from_date, to_date)
		if dates:
			block.covered_from, block.covered_to = dates
			covering.append(block)
	return covering


def get_covered_dates(block, from_date: date, to_date: date) -> tuple[date, date] | None:
	"""The first from and to dates of *block*, or of one of its repeats, that overlap the range.

	Monthly repeats the weekday and its week of the month, so a block on a fifth Sunday covers only
	months that have one. Nothing after Repeat Until is covered.
	"""
	first, last = getdate(block.from_date), getdate(block.to_date)
	if not block.repeat_frequency:
		return (first, last) if first <= to_date and last >= from_date else None

	frequency, interval, _most_days = REPEATS[block.repeat_frequency]
	parts = {}
	if frequency == MONTHLY:
		parts["byweekday"] = weekday(first.weekday())((first.day - 1) // 7 + 1)
	until = getdate(block.repeat_until) if block.repeat_until else None
	length = last - first
	rule = rrule(
		frequency,
		dtstart=datetime.combine(first, time.min),
		interval=interval,
		until=datetime.combine(until, time.min) if until else None,
		**parts,
	)
	start = rule.after(datetime.combine(from_date - length, time.min), inc=True)
	if not start or start.date() > to_date:
		return None
	end = start.date() + length
	return start.date(), min(end, until) if until else end


def get_overlapping_assignments(
	person: str, start, end, exclude_function: str | None = None
) -> list[frappe._dict]:
	"""*person*'s assignments, not declined, at functions that overlap *start* to *end*."""
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	Function = frappe.qb.DocType("Function")
	condition = (
		(Assignment.person == person)
		& (Assignment.status != team_assignment.DECLINED)
		& (Function.start_date <= end.date())
		& (Coalesce(Function.end_date, Function.start_date) >= start.date())
	)
	if exclude_function:
		condition &= Assignment.function != exclude_function

	# church-scope: the one person's own assignments, to warn about double booking
	rows = (
		frappe.qb.from_(Assignment)
		.join(Function)
		.on(Assignment.function == Function.name)
		.select(
			Assignment.title,
			Function.start_date,
			Function.start_time,
			Function.end_date,
			Function.end_time,
			Function.all_day,
		)
		.where(condition)
		.run(as_dict=True)
	)
	return [row for row in rows if overlaps(get_time_window(row), (start, end))]


def overlaps(first: tuple, second: tuple) -> bool:
	return first[0] < second[1] and second[0] < first[1]


def get_check_problem(person: str, position: str, on_date) -> str | None:
	"""Why *person* lacks the checks *position* needs on *on_date*, or None."""
	position_doc = frappe.get_cached_doc("Ministry Team Position", position)
	if not position_doc.needs_background_check:
		return None
	required = [row.check_type for row in position_doc.required_checks]
	return background_check.get_check_problem(person, on_date, required, position_doc.title)


def get_limit_problem(
	person: str, position: str, on_date: date, exclude_function: str | None = None
) -> str | None:
	"""Why *person* has no place left as *position* in the month of *on_date*, or None."""
	position_doc = frappe.get_cached_doc("Ministry Team Position", position)
	limit = next((row.max_times_per_month for row in position_doc.people if row.person == person), 0)
	if not limit:
		return None

	month_start = on_date.replace(day=1)
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	Function = frappe.qb.DocType("Function")
	condition = (
		(Assignment.person == person)
		& (Assignment.position == position)
		& Assignment.status.isin([team_assignment.PENDING, team_assignment.ACCEPTED])
		& (Function.start_date >= month_start)
		& (Function.start_date < month_start + relativedelta(months=1))
	)
	if exclude_function:
		condition &= Assignment.function != exclude_function
	# church-scope: the one person's own assignments to one position, to count them against their limit
	[[count]] = (
		frappe.qb.from_(Assignment)
		.join(Function)
		.on(Assignment.function == Function.name)
		.select(Count(Assignment.name))
		.where(condition)
		.run()
	)
	if count < limit:
		return None
	return _("{0} has reached their limit as {1} in {2}: at most {3} a month.").format(
		frappe.db.get_value("Person", person, "full_name"),
		position_doc.title,
		format_date(on_date, "MMMM yyyy"),
		limit,
	)


def get_problems(
	person: str, start, end, position: str | None = None, exclude_function: str | None = None
) -> list[str]:
	"""Why *person* should not serve from *start* to *end*, as the texts an assignment warns with."""
	problems = [
		_("A Ministry Team Block from {0} to {1} covers this function{2}.").format(
			format_date(block.covered_from),
			format_date(block.covered_to),
			f": {block.reason}" if block.reason else "",
		)
		for block in get_blocks_covering(person, start.date(), end.date())
	]
	person_name = frappe.db.get_value("Person", person, "full_name")
	problems += [
		_("{0} already serves at {1} at the same time.").format(person_name, other.title)
		for other in get_overlapping_assignments(person, start, end, exclude_function)
	]
	if position:
		for problem in (
			get_check_problem(person, position, start.date()),
			get_limit_problem(person, position, start.date(), exclude_function),
		):
			if problem:
				problems.append(problem)
	return problems


def is_available(
	person: str, start, end, position: str | None = None, exclude_function: str | None = None
) -> bool:
	"""Whether *person* is alive and has none of the problems `get_problems` finds."""
	if frappe.db.get_value("Person", person, "is_deceased"):
		return False
	return not get_problems(person, start, end, position, exclude_function)


def rank(candidates: list[str]) -> list[str]:
	"""*candidates* in the order to ask them: who served longest ago (or never) first, then who served least."""
	# church-scope: orders people the caller already chose and shows nothing about them
	people = frappe.get_all(
		"Person",
		filters={"name": ("in", candidates)},
		fields=["name", "last_served_on", "times_served_90d"],
	)
	people.sort(
		key=lambda row: (
			row.last_served_on is not None,
			row.last_served_on or date.min,
			row.times_served_90d or 0,
			row.name,
		)
	)
	return [row.name for row in people]
