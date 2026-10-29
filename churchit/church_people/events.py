# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What changed about a person, for lists and automations to act on.

An app subscribes in its hooks.py, with dotted paths to its handlers:

	churchit_people_events = {"membership_changed": ["my_app.people.on_membership_changed"]}

A handler runs in a background job after the save commits, and receives ``(person, **data)``:

- `membership_changed`: field (one of `membership.TRACKED_FIELDS`), old, new
- `life_event_added`: event_type, date
- `person_deceased`: date

A date is a ``datetime.date`` or None; an empty value is None.
"""

import frappe
from frappe.utils import getdate

from churchit.church_people.membership import TRACKED_FIELDS

HOOK = "churchit_people_events"
MEMBERSHIP_CHANGED = "membership_changed"
LIFE_EVENT_ADDED = "life_event_added"
PERSON_DECEASED = "person_deceased"


def emit(event: str, person: str, **data) -> None:
	"""Run each handler of *event* for *person* in the background, once this transaction commits.

	Install, patches and migrate emit nothing: they move stored data rather than record what happened to a person.
	"""
	if frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate:
		return
	for handler in frappe.get_hooks(HOOK, {}).get(event, []):
		frappe.enqueue(run_handler, enqueue_after_commit=True, handler=handler, person=person, data=data)


def run_handler(handler: str, person: str, data: dict) -> None:
	"""Background job: call *handler* with *person* and the event's *data*.

	The data travels as one dict so its keys cannot clash with `frappe.enqueue`'s own arguments.
	"""
	frappe.get_attr(handler)(person, **data)


def emit_changes(person) -> None:
	"""Emit an event for each change this save made to *person*.

	A new person changes from nothing, so the membership fields they start with and each of their life events count.
	"""
	before = person.get_doc_before_save() or frappe._dict(life_events=[])
	for field in TRACKED_FIELDS:
		old, new = before.get(field) or None, person.get(field) or None
		if old != new:
			emit(MEMBERSHIP_CHANGED, person.name, field=field, old=old, new=new)

	earlier = {row.name for row in before.life_events}
	for row in person.life_events:
		if row.name not in earlier:
			emit(LIFE_EVENT_ADDED, person.name, event_type=row.event_type, date=as_date(row.date))

	if person.is_deceased and not before.is_deceased:
		emit(PERSON_DECEASED, person.name, date=as_date(person.deceased_date))


def as_date(value):
	"""*value* as a date, or None when it is empty."""
	return getdate(value) if value else None
