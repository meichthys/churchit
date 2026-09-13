# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Stop sending the Desk's own Website link back to the Desk.

Frappe consults Portal Settings' default_portal_home before Website Settings when
a logged-in user opens "/", then rewrites a value of "me" to "desk" for System
Users. This app shipped "/me", so staff clicking Website in the Desk sidebar
landed straight back on the Desk and could never reach the public site.

Clears the value only when it still holds the "/me" default this app shipped, so a
church that chose its own landing page keeps it.
"""

import frappe

SHIPPED_DEFAULT = "/me"


def execute():
	if frappe.db.get_single_value("Portal Settings", "default_portal_home") != SHIPPED_DEFAULT:
		return

	frappe.db.set_single_value("Portal Settings", "default_portal_home", "")
