# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the shipped Church Directory print format of Person, so Church Directory always means the report's PDF.

It printed one person on each page, with their ended positions too. A print format that a church made stays.
"""

import frappe

CHURCH_DIRECTORY = "Church Directory"


def execute():
	if frappe.db.get_value("Print Format", CHURCH_DIRECTORY, ["standard", "doc_type"]) != ("Yes", "Person"):
		return
	frappe.db.delete("Property Setter", {"property": "default_print_format", "value": CHURCH_DIRECTORY})
	frappe.delete_doc("Print Format", CHURCH_DIRECTORY, ignore_permissions=True, force=True)
