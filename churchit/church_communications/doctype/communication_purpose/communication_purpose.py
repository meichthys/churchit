# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document

# What a Church Email asks consent for, and what its unsubscribe link withdraws.
CHURCH_NEWS = "Church News"
PASTORAL_CARE = "Pastoral Care"
# What a page from the Check-In Station asks consent for.
CHILD_SAFETY = "Child Safety"
# What a group leader's message, a join request and an attendance reminder ask consent for.
GROUP_MESSAGES = "Group Messages"
# What a reminder of an event the person signed up for asks consent for.
EVENT_REGISTRATIONS = "Event Registrations"
USED_BY_THE_APP = (CHURCH_NEWS, CHILD_SAFETY, GROUP_MESSAGES, EVENT_REGISTRATIONS)

STARTER_PURPOSES = {
	CHURCH_NEWS: "Church Emails: news, events and announcements sent to the congregation.",
	PASTORAL_CARE: "Messages about a person's care, such as visits, prayer and support.",
	CHILD_SAFETY: "Pages from the Check-In Station that ask a child's parents to come.",
	GROUP_MESSAGES: "Messages from group leaders, join requests and their answers, and attendance reminders.",
	EVENT_REGISTRATIONS: "Reminders of the events a person signed up for.",
}


class CommunicationPurpose(Document):
	"""A reason the church contacts people. The purposes the app uses cannot be deleted."""

	def on_trash(self):
		if self.name in USED_BY_THE_APP:
			frappe.throw(_("{0} is used by the app, so it cannot be deleted.").format(frappe.bold(self.name)))


def create_communication_purposes():
	"""Make the starter purposes that are missing. Safe to run again."""
	for purpose, description in STARTER_PURPOSES.items():
		if not frappe.db.exists("Communication Purpose", purpose):
			frappe.get_doc(
				{"doctype": "Communication Purpose", "purpose": purpose, "description": description}
			).insert(ignore_permissions=True)
