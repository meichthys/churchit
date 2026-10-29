# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Take every Person field above permlevel 0 out of the saved Versions of each person.

The form timeline shows a person's Versions to every reader of the person, so a reader without the
permlevel saw medical notes there. `Person.save_version` leaves these fields out of new Versions.
"""

import frappe

from churchit.patches.v1_0.remove_private_fields_from_versions import remove_field_from_versions


def execute():
	for df in frappe.get_meta("Person").fields:
		if df.permlevel:
			remove_field_from_versions("Person", df.fieldname)
