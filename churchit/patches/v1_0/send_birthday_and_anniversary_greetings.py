# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill every person's next birthday and anniversary, and move the copies of the two greetings onto them.

Birthday Greeting and Anniversary Greeting matched the whole date, year included, so they never sent. A church
uses a shipped Notification through a copy, which keeps the old trigger. A copy changes only while it still
sends on the day itself (Days After, 0 days). It keeps the church's own text.
"""

import re

import frappe

from churchit.church_people.derived import refresh_daily

COPY_FILTERS = {"is_standard": 0, "event": "Days After", "days_in_advance": 0}
BIRTH_CONDITION = 'doc.event_type == "Birth" and '
OLD_ANNIVERSARY_CONDITION = "doc.emails and doc.is_primary_contact"
MARRIED = ' and doc.marital_status == "Married"'
BIRTH_ROW_PARENT = re.compile(r"\bdoc\.parent\b")


def execute():
	refresh_daily()
	for name in get_copies("Life Event", "date"):
		move_birthday_greeting(frappe.get_doc("Notification", name))
	for name in get_copies("Person", "anniversary"):
		move_anniversary_greeting(frappe.get_doc("Notification", name))


def get_copies(document_type: str, date_changed: str) -> list[str]:
	return frappe.get_all(
		"Notification",
		filters={**COPY_FILTERS, "document_type": document_type, "date_changed": date_changed},
		pluck="name",
	)


def move_birthday_greeting(copy) -> None:
	"""Send a copy of the Birthday Greeting on the person, who was `doc.parent` of the Birth row."""
	if not (copy.condition or "").startswith(BIRTH_CONDITION):
		return
	copy.update({"document_type": "Person", "event": "Days Before", "date_changed": "next_birthday"})
	copy.condition = read_the_person(copy.condition.removeprefix(BIRTH_CONDITION))
	copy.subject = read_the_person(copy.subject)
	copy.message = read_the_person(copy.message)
	for recipient in copy.recipients:
		recipient.update(
			{field: read_the_person(recipient.get(field)) for field in ("condition", "cc", "bcc")}
		)
	copy.save(ignore_permissions=True)


def read_the_person(template: str | None) -> str | None:
	return BIRTH_ROW_PARENT.sub("doc.name", template) if template else template


def move_anniversary_greeting(copy) -> None:
	"""Send a copy of the Anniversary Greeting on the next anniversary. An unchanged condition also asks for a
	married couple."""
	copy.update({"event": "Days Before", "date_changed": "next_anniversary"})
	if copy.condition == OLD_ANNIVERSARY_CONDITION:
		copy.condition += MARRIED
	copy.save(ignore_permissions=True)
