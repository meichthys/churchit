# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Word the sign-up emails' link "See your sign-up": the link now goes to every registrant who has a login.

Only a copy that still has the shipped text changes. A church's own words stay.
"""

import json
from pathlib import Path

import frappe

OLD_LINK = "See or cancel your sign-up"
TEMPLATES = ("sign_up_confirmation_template", "sign_up_reminder_template")


def execute():
	root = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))
	for folder in TEMPLATES:
		values = json.loads((root / folder / f"{folder}.json").read_text())
		html = frappe.db.get_value("Email Template", values["name"], "response_html")
		if (
			html
			and OLD_LINK in html
			and html.replace(OLD_LINK, "See your sign-up") == values["response_html"]
		):
			frappe.db.set_value("Email Template", values["name"], "response_html", values["response_html"])
