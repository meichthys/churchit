# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Serving: when a person last served on a ministry team, how often in 90 days, and the positions that list them."""

import frappe
from frappe.query_builder.functions import Coalesce, Count, Max
from frappe.utils import add_days, getdate, nowdate
from pypika import Case

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import ACCEPTED
from churchit.church_people.summaries import same_church

FIELDS = ("last_served_on", "times_served_90d", "ministry_teams", "team_positions")
WINDOW_DAYS = 90
INACTIVE = "Inactive"


def assignment_people(doc) -> set[str]:
	before = doc.get_doc_before_save()
	return {doc.person, before.person} if before else {doc.person}


def function_assignees(doc) -> set[str]:
	"""Everyone assigned to the function, whose serving dates move with its date and church."""
	# church-scope: names the people to refresh and shows nobody anything
	return set(frappe.get_all("Ministry Team Assignment", filters={"function": doc.name}, pluck="person"))


def position_people(doc) -> set[str]:
	before = doc.get_doc_before_save()
	rows = [*(doc.get("people") or []), *(before.get("people") or [] if before else [])]
	return {row.person for row in rows}


def ministry_people(doc) -> set[str]:
	"""Everyone on the ministry's positions, when its status or church changes."""
	if not (doc.has_value_changed("status") or doc.has_value_changed("church")):
		return set()
	# church-scope: names the people to refresh and shows nobody anything
	return set(
		frappe.get_all(
			"Ministry Team Position", filters={"ministry": doc.name}, fields=["people.person"], pluck="person"
		)
	)


SOURCES = {
	"Ministry Team Assignment": assignment_people,
	"Function": function_assignees,
	"Ministry Team Position": position_people,
	"Ministry": ministry_people,
}


def compute(people: list[str]) -> dict[str, dict]:
	summaries = get_times_served(people)
	for row in get_positions(people):
		summary = summaries.setdefault(row.person, {})
		summary.setdefault("team_positions", []).append(row.position)
		teams = summary.setdefault("ministry_teams", [])
		if row.ministry not in teams:
			teams.append(row.ministry)
	return summaries


def get_times_served(people: list[str]) -> dict[str, dict]:
	"""Each person's last accepted function up to today, and the accepted functions in the window.

	The function's church is compared, not the assignment's: the assignment copies it when saved and keeps the
	old one when the function is shared later.
	"""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared functions
	Assignment = frappe.qb.DocType("Ministry Team Assignment")
	Function = frappe.qb.DocType("Function")
	Person = frappe.qb.DocType("Person")
	today = getdate(nowdate())
	since = add_days(today, -WINDOW_DAYS)
	rows = (
		frappe.qb.from_(Assignment)
		.join(Function)
		.on(Function.name == Assignment.function)
		.join(Person)
		.on(Person.name == Assignment.person)
		.select(
			Assignment.person,
			Max(Function.start_date).as_("last"),
			Count(Case().when(Function.start_date >= since, Function.name)).distinct().as_("recent"),
		)
		.where(Assignment.person.isin(people) & (Assignment.status == ACCEPTED))
		.where(Function.start_date <= today)
		.where(same_church(Function, Person))
		.groupby(Assignment.person)
		.run(as_dict=True)
	)
	return {row.person: {"last_served_on": row.last, "times_served_90d": row.recent} for row in rows}


def get_positions(people: list[str]) -> list[dict]:
	"""The positions that list each person, with their ministry if it is not Inactive, by ministry and position name."""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared positions
	Member = frappe.qb.DocType("Ministry Team Position Person")
	Position = frappe.qb.DocType("Ministry Team Position")
	Ministry = frappe.qb.DocType("Ministry")
	Person = frappe.qb.DocType("Person")
	return (
		frappe.qb.from_(Member)
		.join(Position)
		.on((Position.name == Member.parent) & (Member.parenttype == "Ministry Team Position"))
		.join(Ministry)
		.on(Ministry.name == Position.ministry)
		.join(Person)
		.on(Person.name == Member.person)
		.select(Member.person, Position.name.as_("position"), Position.ministry)
		.distinct()
		.where(Member.person.isin(people) & (Coalesce(Ministry.status, "") != INACTIVE))
		.where(same_church(Position, Person))
		.orderby(Ministry.ministry_name)
		.orderby(Position.position_name)
		.run(as_dict=True)
	)
