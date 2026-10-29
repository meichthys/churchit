# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A person's place in the church, on two fields.

`membership` (a Membership Type) is how they are connected: Member, Regular
Attender, Visitor or Contact. `membership_status` (a Member Status) is whether
they still take part: Active or Inactive, for everyone. An active member has both.
"""

import frappe

MEMBER = "Member"
REGULAR_ATTENDER = "Regular Attender"
VISITOR = "Visitor"
CONTACT = "Contact"
MEMBERSHIP_TYPES = (MEMBER, REGULAR_ATTENDER, VISITOR, CONTACT)

ACTIVE = "Active"
INACTIVE = "Inactive"
MEMBER_STATUSES = (ACTIVE, INACTIVE)

# Each new value of these is kept as a Milestone, the membership history.
TRACKED_FIELDS = ("membership", "membership_status")


def is_active_member(Person):
	"""Query criterion for an active member on the Person table *Person*."""
	return (Person.membership == MEMBER) & (Person.membership_status == ACTIVE)


def living_people_filter(Person=None):
	"""Query criterion for the people who have not died, on the Person table *Person* or an alias of it.

	It is the one rule for who has died, in `frappe.qb` and as an item of a `frappe.get_list` filters list.
	A Death life event sets `is_deceased` on save.
	"""
	# church-scope: builds a criterion and reads nothing; the query or get_list it joins applies the scope
	Person = Person or frappe.qb.DocType("Person")
	return Person.is_deceased == 0


def record_changes(person, method=None):
	"""Keep a Milestone for each tracked field this save gave a new value; a cleared field keeps none.

	Frappe's Milestone Tracker takes one field per doctype and fails a save that clears it, so the
	Milestones are written here. Install, patches and migrate keep none: they move stored data.
	"""
	if frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate:
		return
	before = person.get_doc_before_save()
	for field in TRACKED_FIELDS:
		value = person.get(field)
		if value and value != (before.get(field) if before else None):
			frappe.get_doc(
				{
					"doctype": "Milestone",
					"reference_type": "Person",
					"reference_name": person.name,
					"track_field": field,
					"value": value,
				}
			).insert(ignore_permissions=True)


def changed_between(field: str, value: str, start, end) -> set[str]:
	"""The people whose *field* changed to *value* from the *start* date to the *end* date, both included.

	It reads every church's Milestones: the caller scopes the people it gets back.
	"""
	# church-scope: Milestones carry no church; the caller narrows the people to the reader's churches
	return set(
		frappe.get_all(
			"Milestone",
			filters={
				"reference_type": "Person",
				"track_field": field,
				"value": value,
				"creation": ("between", [start, end]),
			},
			pluck="reference_name",
		)
	)
