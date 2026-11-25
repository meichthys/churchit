# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Delete the shipped member web forms: the member app at /portal took their place.

Frappe's web form APIs read and saved records through these forms. Their old addresses open the app
(hooks.py website_redirects). A web form that a church made stays.
"""

import frappe

# The record names. care-request-form serves /care-request.
WEB_FORMS = (
	"personal-details",
	"function-sign-up",
	"room-request",
	"groups",
	"group-files",
	"prayer-request",
	"community-prayer-requests",
	"care-request-form",
	"alms-request",
	"pledge",
)


def execute():
	shipped = frappe.get_all("Web Form", filters={"name": ("in", WEB_FORMS), "is_standard": 1}, pluck="name")
	for name in shipped:
		frappe.delete_doc("Web Form", name, ignore_permissions=True, force=True)
