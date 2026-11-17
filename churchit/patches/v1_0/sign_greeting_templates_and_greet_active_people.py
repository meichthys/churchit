# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Sign three starter email templates with the church name, and send the two greetings to active people only.

A template changes only while it still ends with the shipped sign-off, and a greeting copy only while it has
the shipped condition. A church's own words stay, and each copy stays enabled or disabled as it was.
"""

import frappe

SIGN_OFFS = {
	"Birthday Greeting": ("<br>The Church</p>", "<br>{{ church_name }}</p>"),
	"New Member Welcome": ("<br>The Pastoral Team</p>", "<br>The Pastoral Team at {{ church_name }}</p>"),
	"Visitor Follow-Up": ("<br>The Welcome Team</p>", "<br>The Welcome Team at {{ church_name }}</p>"),
}
ACTIVE = ' and doc.membership_status == "Active"'
SHIPPED_CONDITIONS = {
	"next_birthday": ("doc.primary_email",),
	"next_anniversary": ('doc.emails and doc.is_primary_contact and doc.marital_status == "Married"',),
}


def execute():
	for name, (old, new) in SIGN_OFFS.items():
		html = frappe.db.get_value("Email Template", name, "response_html")
		if html and html.endswith(old):
			frappe.db.set_value("Email Template", name, "response_html", html.removesuffix(old) + new)

	for date_changed, conditions in SHIPPED_CONDITIONS.items():
		for copy in frappe.get_all(
			"Notification",
			filters={
				"is_standard": 0,
				"document_type": "Person",
				"date_changed": date_changed,
				"condition": ("in", conditions),
			},
			pluck="name",
		):
			condition = frappe.db.get_value("Notification", copy, "condition")
			frappe.db.set_value("Notification", copy, "condition", condition + ACTIVE)
