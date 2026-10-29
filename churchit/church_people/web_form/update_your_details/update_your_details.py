# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe


def get_context(context):
	# Frappe sends a guest no virtual fields, so the link holder's own birth date is added back.
	if context.reference_doc and context.reference_doc.get("name"):
		# church-scope: the one Person the link's key opens, which Frappe checked
		context.reference_doc["birthday"] = frappe.db.get_value(
			"Person", context.reference_doc["name"], "birth_date"
		)
