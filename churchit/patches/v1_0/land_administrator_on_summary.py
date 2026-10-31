# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Open Summary for Administrator after login on sites installed after the move to the Apps screen.

Frappe creates Administrator before churchit is installed, so it never got Summary, and as the
holder of every role it opened the check-in kiosk instead.
"""

import frappe

from churchit.church_summary.home import SUMMARY


def execute():
	if not frappe.db.get_value("User", "Administrator", "default_workspace"):
		frappe.db.set_value("User", "Administrator", "default_workspace", SUMMARY)
