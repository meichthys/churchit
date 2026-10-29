# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the Mailing Labels (Avery 5160) print format; Household Label replaces it.

Bulk Print gives each family its own page, so it never printed a sheet of labels.
"""

import frappe

AVERY_LABELS = "Mailing Labels (Avery 5160)"


def execute():
	frappe.db.delete(
		"Property Setter", {"doc_type": "Family", "property": "default_print_format", "value": AVERY_LABELS}
	)
	frappe.delete_doc_if_exists("Print Format", AVERY_LABELS)
