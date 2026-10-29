# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Delete the onboarding step and form tour that explained the nightly member Email Groups.

Church Emails replaced those groups, and Frappe keeps a step or a tour on a site after its file
is gone from the app.
"""

import frappe

NAME = "Email Group"


def execute():
	for doctype in ("Onboarding Step", "Form Tour"):
		frappe.delete_doc_if_exists(doctype, NAME, force=True)
