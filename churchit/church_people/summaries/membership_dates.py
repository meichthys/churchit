# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Membership dates: when a person's Membership and Status last changed, from their Milestones."""

import frappe
from frappe.query_builder.functions import Max

from churchit.church_people.membership import TRACKED_FIELDS
from churchit.query import Date

FIELDS = ("membership_changed_on", "status_changed_on")
CHANGED_ON = dict(zip(TRACKED_FIELDS, FIELDS, strict=True))


def milestone_people(doc) -> set[str]:
	return {doc.reference_name} if doc.reference_type == "Person" else set()


SOURCES = {"Milestone": milestone_people}


def compute(people: list[str]) -> dict[str, dict]:
	"""The date of each person's latest Milestone for each tracked field."""
	# church-scope: stored on the person; a Milestone carries no church and belongs to the person it names
	Milestone = frappe.qb.DocType("Milestone")
	rows = (
		frappe.qb.from_(Milestone)
		.select(
			Milestone.reference_name, Milestone.track_field, Max(Date(Milestone.creation)).as_("changed_on")
		)
		.where((Milestone.reference_type == "Person") & Milestone.reference_name.isin(people))
		.where(Milestone.track_field.isin(TRACKED_FIELDS))
		.groupby(Milestone.reference_name, Milestone.track_field)
		.run(as_dict=True)
	)
	summaries = {}
	for row in rows:
		summaries.setdefault(row.reference_name, {})[CHANGED_ON[row.track_field]] = row.changed_on
	return summaries
