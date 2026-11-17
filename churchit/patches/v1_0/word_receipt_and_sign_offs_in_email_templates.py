# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fix the Donation Acknowledgment wording and sign the sign-up emails with the church name.

Only a copy that still has the shipped text gets the new text. A church's own words stay.
"""

import json
from pathlib import Path

import frappe

SHIPPED = {
	"donation_acknowledgment_template": (
		"<p>Dear {{ first_name }},</p>\n\n<p>Thank you for your gift of {{ amount }} to the {{ fund }} on "
		"{{ date }}.</p>\n\n<p>A formal receipt is attached for your records. No goods or services were "
		"exchanged for this gift.</p>\n\n<p>With gratitude,<br>The Treasury Team</p>"
	),
	"sign_up_confirmation_template": (
		"<p>Dear {{ first_name | e }},</p>\n\n<p>You are registered for <strong>{{ function_name | e }}"
		"</strong> on {{ date }}{% if time %} at {{ time }}{% endif %}.</p>\n\n{% if attendees | length > 1 %}"
		'<p>Attending: {{ attendees | join(", ") | e }}</p>\n\n{% endif %}<p>To add the event to your '
		"calendar, open the attached file.</p>\n\n<p>We look forward to seeing you!</p>"
	),
	"sign_up_reminder_template": (
		"<p>Dear {{ first_name }},</p>\n\n<p>This is a reminder that you signed up for <strong>"
		"{{ function_name }}</strong> on {{ date }}{% if time %} at {{ time }}{% endif %}.</p>\n\n"
		"<p>We look forward to seeing you!</p>"
	),
	"sign_up_payment_due_template": (
		"<p>Dear {{ first_name | e }},</p>\n\n<p>Thank you for registering for <strong>"
		"{{ function_name | e }}</strong> on {{ date }}{% if time %} at {{ time }}{% endif %}. Your place is "
		"held for you until {{ pay_by }}. The amount due is {{ amount }}.</p>\n\n{% if pay_url %}<p><a "
		'href="{{ pay_url }}">Pay now</a></p>{% else %}<p>Please pay the church office before then.</p>'
		"{% endif %}\n\n<p>If it is not paid by then, the registration is cancelled.</p>"
	),
}


def execute():
	root = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))
	for folder, shipped_html in SHIPPED.items():
		values = json.loads((root / folder / f"{folder}.json").read_text())
		if frappe.db.get_value("Email Template", values["name"], "response_html") == shipped_html:
			frappe.db.set_value("Email Template", values["name"], "response_html", values["response_html"])
