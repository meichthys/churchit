# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Access Log entries for the exports Frappe leaves unlogged.

Frappe logs a list or Report Builder export, a print, a PDF and a report export, but not the Export Data
dialog of Data Import, which writes out whole records with their child tables: every email, phone and
address of every person.
"""

import frappe
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.doctype.data_import import data_import


@frappe.whitelist()
def download_template(
	doctype: str,
	export_fields: str | dict | None = None,
	export_records: str | None = None,
	export_filters: str | dict | list | None = None,
	file_type: str = "CSV",
):
	"""override_whitelisted_methods for Data Import's export: Frappe's own, logged when it carries records."""
	data_import.download_template(doctype, export_fields, export_records, export_filters, file_type)
	if export_records != "blank_template":
		make_access_log(doctype=doctype, file_type=file_type, method="Export Data", filters=export_filters)
