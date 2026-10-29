# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

# A church's starting interests, with what each one offers a guest.
STARTER_INTERESTS = (
	("Join a group", "Find a small group to grow and pray with."),
	("Serve on a team", "Help with greeting, music, children or another ministry."),
	("Learn about baptism", "Hear what baptism means and how to be baptized."),
	("Learn about membership", "Hear what membership means and how to become a member."),
	("Talk with a pastor", "Have a pastor get in touch."),
)


class ConnectionCardInterest(Document):
	"""Something a guest can tick on the Connection Card web form."""


def create_connection_card_interests():
	"""Make the starting interests a church does not have yet."""
	for interest, description in STARTER_INTERESTS:
		if not frappe.db.exists("Connection Card Interest", interest):
			frappe.get_doc(
				{"doctype": "Connection Card Interest", "interest": interest, "description": description}
			).insert(ignore_permissions=True)
