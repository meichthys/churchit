# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give the sign-up emails a link to the sign-up and the amount to pay at the church, and point the welcome
email to the Member Portal.

Only a copy that still has the shipped text gets the new text. A church's own words stay.
"""

import json
from pathlib import Path

import frappe

# The shipped text before this patch. word_receipt_and_sign_offs_in_email_templates leaves it in the sign-up emails.
SHIPPED = {
	"sign_up_confirmation_template": (
		"<p>Dear {{ first_name | e }},</p>\n\n<p>You are registered for <strong>{{ function_name | e }}"
		"</strong> on {{ date }}{% if time %} at {{ time }}{% endif %}.</p>\n\n{% if attendees | length > 1 %}"
		'<p>Attending: {{ attendees | join(", ") | e }}</p>\n\n{% endif %}<p>To add the event to your '
		"calendar, open the attached file.</p>\n\n<p>We look forward to seeing you!</p>\n\n<p>{{ church_name }}</p>"
	),
	"sign_up_reminder_template": (
		"<p>Dear {{ first_name }},</p>\n\n<p>This is a reminder that you signed up for <strong>"
		"{{ function_name }}</strong> on {{ date }}{% if time %} at {{ time }}{% endif %}.</p>\n\n"
		"<p>We look forward to seeing you!</p>\n\n<p>{{ church_name }}</p>"
	),
	"new_member_welcome_template": (
		"<p>Dear {{ first_name }},</p>\n\n<p>Welcome to our church family! We are thrilled to have you as a "
		"member of our congregation.</p>\n\n<p>Our pastor or one of our deacons will reach out to you shortly. "
		"In the meantime, please don't hesitate to contact us with any questions or needs.</p>\n\n<p>\"So then "
		"you are no longer strangers and aliens, but you are fellow citizens with the saints and members of the "
		'household of God." - Ephesians 2:19</p>\n\n<p>In Christ,<br>The Pastoral Team</p>'
	),
}


def execute():
	root = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))
	for folder, shipped_html in SHIPPED.items():
		values = json.loads((root / folder / f"{folder}.json").read_text())
		if frappe.db.get_value("Email Template", values["name"], "response_html") == shipped_html:
			frappe.db.set_value("Email Template", values["name"], "response_html", values["response_html"])
