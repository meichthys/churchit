# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give each fund ledger row of a Collection the date of its Collection.

A Collection dated its ledger rows with the time it was submitted, so a Collection entered late
showed in the wrong month of the fund reports. A row now takes the date of its Collection.
"""

import frappe


def execute():
	Transaction = frappe.qb.DocType("Financial Transaction")
	Collection = frappe.qb.DocType("Collection")
	rows = (
		frappe.qb.from_(Transaction)
		.join(Collection)
		.on(Collection.name == Transaction.source)
		.select(Transaction.name, Collection.date)
		.where((Transaction.source_type == "Collection") & (Transaction.date != Collection.date))
		.run(as_dict=True)
	)
	for row in rows:
		frappe.db.set_value("Financial Transaction", row.name, "date", row.date, update_modified=False)
