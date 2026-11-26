# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.contacts import PHONE_DOCTYPE, format_phone_number

PHONE_FIELDS = (
	(PHONE_DOCTYPE, "phone_number"),
	("Person", "primary_phone"),
	("Person", "emergency_contact_phone"),
	("Church", "phone"),
	("Connection Card", "phone"),
	("Function Sign-Up", "phone"),
)


def execute():
	"""Format each phone number saved before Churchit formatted them, such as 2025550123 as (202) 555-0123."""
	for doctype, fieldname in PHONE_FIELDS:
		for row in frappe.get_all(doctype, filters={fieldname: ("is", "set")}, fields=["name", fieldname]):
			formatted = format_phone_number(row[fieldname])
			if formatted != row[fieldname]:
				frappe.db.set_value(doctype, row.name, fieldname, formatted, update_modified=False)
