# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Turn the past changes of each person's Membership and Status, kept in Versions, into Milestones.

The history then starts before this release. Each person also gets their first known value, dated
when they were added. A change already kept within a minute of the same time is skipped, so a rerun
or a save made during the upgrade is not counted twice.
"""

import json
from datetime import timedelta

import frappe

from churchit.church_people.membership import TRACKED_FIELDS

SAME_CHANGE = timedelta(minutes=1)


def execute():
	kept = get_kept_milestones()
	changes = get_version_changes()
	for person in frappe.get_all("Person", fields=["name", "creation", "owner", *TRACKED_FIELDS]):
		for field in TRACKED_FIELDS:
			for change in get_history(person, field, changes.get((person.name, field), [])):
				if change.value and not is_kept(kept.get((person.name, field, change.value), []), change):
					insert_milestone(person.name, field, change)


def get_kept_milestones() -> dict[tuple, list]:
	"""{(person, field, value): [when]} of the Milestones already kept."""
	kept = {}
	for milestone in frappe.get_all(
		"Milestone",
		filters={"reference_type": "Person", "track_field": ("in", TRACKED_FIELDS)},
		fields=["reference_name", "track_field", "value", "creation"],
	):
		key = (milestone.reference_name, milestone.track_field, milestone.value)
		kept.setdefault(key, []).append(milestone.creation)
	return kept


def is_kept(times: list, change) -> bool:
	"""True when a Milestone of the same value was kept at about the time of *change*."""
	return any(abs(time - change.at) <= SAME_CHANGE for time in times)


def get_version_changes() -> dict[tuple, list]:
	"""{(person, field): [change]} from the Person Versions, oldest first."""
	changes = {}
	for version in frappe.get_all(
		"Version",
		filters={"ref_doctype": "Person", "data": ("like", "%membership%")},
		fields=["docname", "data", "creation", "owner"],
		order_by="creation asc",
	):
		for field, old, new in json.loads(version.data).get("changed", []):
			if field in TRACKED_FIELDS:
				changes.setdefault((version.docname, field), []).append(
					frappe._dict(at=version.creation, owner=version.owner, old=old, value=new)
				)
	return changes


def get_history(person, field: str, changes: list) -> list:
	"""*person*'s first value of *field*, when they were added, followed by each of its *changes*."""
	first = changes[0].old if changes else person[field]
	return [frappe._dict(at=person.creation, owner=person.owner, value=first), *changes]


def insert_milestone(person: str, field: str, change):
	frappe.get_doc(
		{
			"doctype": "Milestone",
			"reference_type": "Person",
			"reference_name": person,
			"track_field": field,
			"value": change.value,
			"creation": change.at,
			"modified": change.at,
			"owner": change.owner,
			"modified_by": change.owner,
		}
	).db_insert()
