# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give the Room Booking Decided Notification a link to the booking, while it holds the text this app inserted.

A member's link opens their request on the Room Request page, and a staff member's opens the desk form. A message
the church changed stays as it is.
"""

import frappe

from churchit.church_operations.doctype.room_booking.room_booking import DECIDED_MESSAGE, DECIDED_NOTIFICATION

# The message as add_room_booking_decided_notification and format_dates_and_money_in_inserted_notifications left it.
SHIPPED_MESSAGE = """<p>Your room booking is {{ doc.status | lower }}.</p>

<ul>
  {% if doc.room %}<li><strong>Room:</strong> {{ frappe.db.get_value("Room", doc.room, "room_name") }}</li>{% endif %}
  <li><strong>Purpose:</strong> {{ doc.purpose }}</li>
  <li><strong>Start:</strong> {{ frappe.utils.format_datetime(doc.start_datetime, "EEEE, MMMM d, yyyy h:mm a") }}</li>
  <li><strong>End:</strong> {{ frappe.utils.format_datetime(doc.end_datetime, "EEEE, MMMM d, yyyy h:mm a") }}</li>
</ul>
"""


def execute():
	if frappe.db.get_value("Notification", DECIDED_NOTIFICATION, "message") == SHIPPED_MESSAGE:
		frappe.db.set_value("Notification", DECIDED_NOTIFICATION, "message", DECIDED_MESSAGE)
