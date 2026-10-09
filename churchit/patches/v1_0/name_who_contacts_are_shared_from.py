"""Replace the Shared tick box on emails and phones with Shared From.

A ticked row is shared from the oldest unticked row of the same value on another
record of its doctype. A ticked row with no such owner is left unshared.
"""

import frappe

from churchit.contacts import EMAIL_DOCTYPE, PHONE_DOCTYPE, contact_key


def execute():
	for child_doctype, value_field in ((EMAIL_DOCTYPE, "email_address"), (PHONE_DOCTYPE, "phone_number")):
		table = frappe.qb.DocType(child_doctype)
		frappe.qb.update(table).set(table.shared_from_type, table.parenttype).run()
		if frappe.db.has_column(child_doctype, "is_shared"):
			share_ticked_rows(child_doctype, value_field)


def share_ticked_rows(child_doctype, value_field):
	table = frappe.qb.DocType(child_doctype)
	rows = (
		frappe.qb.from_(table)
		.select(table.name, table.parenttype, table.parent, table[value_field], table.is_shared)
		.where(table[value_field].isnotnull() & (table[value_field] != ""))
		.orderby(table.creation)
		.run(as_dict=True)
	)
	owners = {}
	for row in rows:
		if not row.is_shared:
			owners.setdefault((row.parenttype, contact_key(child_doctype, row[value_field])), row.parent)
	for row in rows:
		owner = owners.get((row.parenttype, contact_key(child_doctype, row[value_field])))
		if row.is_shared and owner and owner != row.parent:
			frappe.db.set_value(child_doctype, row.name, "shared_from", owner, update_modified=False)
