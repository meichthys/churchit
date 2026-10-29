# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Care: open care requests, the last visit, and the latest background check."""

import frappe
from frappe.query_builder import Order
from frappe.query_builder.functions import Coalesce, Count, Max
from frappe.utils import getdate, nowdate
from pypika import Case

from churchit.church_people.summaries import same_church

FIELDS = ("open_care_requests", "last_visited_on", "background_check_status", "background_check_expires_on")
FINISHED = ("Resolved", "Closed")
COMPLETED = "Completed"
CLEARED = "Cleared"
EXPIRED = "Expired"


def record_people(doc) -> set[str]:
	before = doc.get_doc_before_save()
	return {doc.person, before.person} if before else {doc.person}


SOURCES = {"Care Request": record_people, "Visitation Log": record_people, "Background Check": record_people}


def compute(people: list[str]) -> dict[str, dict]:
	summaries = {}
	for found in (get_open_care_requests(people), get_last_visits(people), get_background_checks(people)):
		for person, values in found.items():
			summaries.setdefault(person, {}).update(values)
	return summaries


def get_open_care_requests(people: list[str]) -> dict[str, dict]:
	"""How many of each person's care requests are not yet Resolved or Closed."""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared requests
	Request = frappe.qb.DocType("Care Request")
	Person = frappe.qb.DocType("Person")
	rows = (
		frappe.qb.from_(Request)
		.join(Person)
		.on(Person.name == Request.person)
		.select(Request.person, Count(Request.name).as_("open"))
		.where(Request.person.isin(people) & Coalesce(Request.status, "").notin(FINISHED))
		.where(same_church(Request, Person))
		.groupby(Request.person)
		.run(as_dict=True)
	)
	return {row.person: {"open_care_requests": row.open} for row in rows}


def get_last_visits(people: list[str]) -> dict[str, dict]:
	"""Each person's latest completed visit up to today."""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared visits
	Visit = frappe.qb.DocType("Visitation Log")
	Person = frappe.qb.DocType("Person")
	rows = (
		frappe.qb.from_(Visit)
		.join(Person)
		.on(Person.name == Visit.person)
		.select(Visit.person, Max(Visit.visit_date).as_("last"))
		.where(Visit.person.isin(people) & (Visit.status == COMPLETED))
		.where(Visit.visit_date <= getdate(nowdate()))
		.where(same_church(Visit, Person))
		.groupby(Visit.person)
		.run(as_dict=True)
	)
	return {row.person: {"last_visited_on": row.last} for row in rows}


def get_background_checks(people: list[str]) -> dict[str, dict]:
	"""Each person's most recent background check, by the Person form's rule: the latest requested_on first.

	A tie goes to the check entered last, and a blank requested_on sorts as the oldest. A cleared check past its
	expiry reads as Expired straight away, whichever of today's scheduled jobs runs first.
	"""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared checks
	Check = frappe.qb.DocType("Background Check")
	Person = frappe.qb.DocType("Person")
	is_past_expiry = (Check.status == CLEARED) & (Check.expires_on < getdate(nowdate()))
	rows = (
		frappe.qb.from_(Check)
		.join(Person)
		.on(Person.name == Check.person)
		.select(
			Check.person,
			Case().when(is_past_expiry, EXPIRED).else_(Check.status).as_("status"),
			Check.expires_on,
		)
		.where(Check.person.isin(people))
		.where(same_church(Check, Person))
		.orderby(Check.requested_on, order=Order.desc)
		.orderby(Check.creation, order=Order.desc)
		.run(as_dict=True)
	)
	summaries = {}
	for row in rows:
		if row.person not in summaries:
			summaries[row.person] = {
				"background_check_status": row.status,
				"background_check_expires_on": row.expires_on,
			}
	return summaries
