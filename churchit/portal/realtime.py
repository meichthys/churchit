# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Live-update hints for the member app tabs a user has open.

A hint names only what changed: a topic, such as "sign-ups", and maybe a record name. The app then reads
the data again through its permission-checked GET. Delivery is best effort, so the app also reads again
when its socket reconnects and when a tab comes back into view. Never broadcast to a doctype room:
Frappe's list_update tells every reader of a doctype which record changed and who saved it.
"""

import frappe

EVENT = "churchit_portal"


def notify(user: str | None, topic: str, name: str | None = None) -> None:
	"""Tell *user*'s open app tabs that *topic* changed, once the transaction commits."""
	if not user or user == "Guest":
		return
	frappe.publish_realtime(EVENT, {"topic": topic, "name": name}, user=user, after_commit=True)


def notify_person(person: str | None, topic: str, name: str | None = None) -> None:
	"""notify() the login of *person*, when they have one."""
	if person:
		notify(frappe.db.get_value("Person", person, "user"), topic, name)
