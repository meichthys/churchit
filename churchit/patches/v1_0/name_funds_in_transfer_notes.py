# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Name the other fund in a transfer's ledger notes, 'Transfer to Building', not its ID 'Transfer to FUND-0004'."""

import frappe

from churchit.church_finances.doctype.fund_transfer.fund_transfer import get_fund_labels


def execute():
	Transaction = frappe.qb.DocType("Financial Transaction")
	Transfer = frappe.qb.DocType("Fund Transfer")
	rows = (
		frappe.qb.from_(Transaction)
		.join(Transfer)
		.on(Transaction.source == Transfer.name)
		.select(Transaction.name, Transaction.notes, Transfer.from_fund, Transfer.to_fund)
		.where((Transaction.source_type == "Fund Transfer") & Transaction.notes.like("Transfer %"))
		.run(as_dict=True)
	)
	for row in rows:
		notes = get_notes_with_fund_names(row.notes, row.from_fund, row.to_fund)
		if notes != row.notes:
			frappe.db.set_value("Financial Transaction", row.name, "notes", notes, update_modified=False)


def get_notes_with_fund_names(notes: str, from_fund: str, to_fund: str) -> str:
	"""*notes* with a leading 'Transfer to <fund ID>' or 'Transfer from <fund ID>' given the fund's name."""
	from_label, to_label = get_fund_labels(from_fund, to_fund)
	for old, new in (
		(f"Transfer to {to_fund}", f"Transfer to {to_label}"),
		(f"Transfer from {from_fund}", f"Transfer from {from_label}"),
	):
		rest = notes[len(old) :]
		if notes.startswith(old) and (not rest or rest.startswith(":")):
			return new + rest
	return notes
