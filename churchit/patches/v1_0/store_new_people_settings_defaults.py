# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Store the default of each People Settings field added after a site first saved its settings.

Frappe reads a Single field that was never saved as empty, not as its default, so the school year
would have no start month.
"""

import frappe

from churchit.church_people.doctype.people_settings.people_settings import store_defaults


def execute():
	store_defaults()
	stored = frappe.db.get_singles_dict("People Settings")
	for field in frappe.get_meta("People Settings").fields:
		if field.default is not None and field.fieldname not in stored:
			frappe.db.set_single_value("People Settings", field.fieldname, field.default)
