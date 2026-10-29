# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Store the default of each Check-In Settings field added after a site first saved its settings.

Frappe reads a Single field that was never saved as empty, not as its default, so Room Capacity would
be blank and self check-in would open 0 minutes before a Function.
"""

import frappe


def execute():
	stored = frappe.db.get_singles_dict("Check-In Settings")
	if not stored:
		return
	for field in frappe.get_meta("Check-In Settings").fields:
		if field.default is not None and field.fieldname not in stored:
			frappe.db.set_single_value("Check-In Settings", field.fieldname, field.default)
