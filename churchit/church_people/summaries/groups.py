# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Groups: the groups a person belongs to that are still meeting, and how many."""

import frappe
from frappe.query_builder.functions import Coalesce

from churchit.church_people.summaries import same_church

FIELDS = ("groups", "group_count")
INACTIVE = "Inactive"


def group_members(doc) -> set[str]:
	before = doc.get_doc_before_save()
	rows = [*(doc.get("members") or []), *(before.get("members") or [] if before else [])]
	return {row.person for row in rows}


SOURCES = {"Group": group_members}


def compute(people: list[str]) -> dict[str, dict]:
	"""Each person's groups that are not Inactive, by group name."""
	# church-scope: stored on the person; same_church keeps it to their own church's and shared groups
	Member = frappe.qb.DocType("Group Member")
	Group = frappe.qb.DocType("Group")
	Person = frappe.qb.DocType("Person")
	rows = (
		frappe.qb.from_(Member)
		.join(Group)
		.on((Group.name == Member.parent) & (Member.parenttype == "Group"))
		.join(Person)
		.on(Person.name == Member.person)
		.select(Member.person, Group.name)
		.distinct()
		.where(Member.person.isin(people) & (Coalesce(Group.status, "") != INACTIVE))
		.where(same_church(Group, Person))
		.orderby(Group.group_name)
		.run(as_dict=True)
	)
	summaries = {}
	for row in rows:
		summary = summaries.setdefault(row.person, {"groups": [], "group_count": 0})
		summary["groups"].append(row.name)
		summary["group_count"] += 1
	return summaries
