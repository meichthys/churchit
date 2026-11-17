# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Set an Approved alms request that a submitted expense pays to Distributed, as Create Expense now does.

Pending Alms Requests lists every Approved request as one that waits for its expense.
"""

import frappe


def execute():
	AlmsRequest = frappe.qb.DocType("Alms Request")
	Expense = frappe.qb.DocType("Expense")
	paid = (
		frappe.qb.from_(AlmsRequest)
		.inner_join(Expense)
		.on(Expense.name == AlmsRequest.associated_expense)
		.select(AlmsRequest.name)
		.where((AlmsRequest.status == "Approved") & (Expense.docstatus == 1))
		.run(pluck=True)
	)
	for name in paid:
		frappe.db.set_value("Alms Request", name, "status", "Distributed", update_modified=False)
