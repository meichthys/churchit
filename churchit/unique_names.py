# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Refuse a second record with the name a church's list already shows."""

import frappe
from frappe.model.document import Document
from frappe.utils import cint, escape_html

from churchit.church_scope import church_filters, default_church


def refuse_a_second_with_this_name(doc: Document, fieldname: str, message: str) -> None:
	"""Throw *message* (with the name as {0}) when another record of the church has this name.

	Only a new or changed name, church or sharing is checked, so a record saved before this check can still
	be saved. A shared record is compared with every church's records, as every church lists it.
	"""
	name = doc.get(fieldname)
	if not name or not any(doc.has_value_changed(field) for field in (fieldname, "church", "is_shared")):
		return

	filters = {fieldname: name, "name": ("!=", doc.name or "")}
	if not cint(doc.get("is_shared")):
		church = doc.get("church") or doc.get("shared_by_church") or default_church()
		filters = church_filters(church, **filters)

	# church-scope: a name must not repeat among the records one church lists, whoever owns them
	if frappe.db.exists(doc.doctype, filters):
		frappe.throw(message.format(frappe.bold(escape_html(name))))
