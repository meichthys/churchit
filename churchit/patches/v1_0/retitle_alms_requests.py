# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Title each alms request with its recipient's name, and the expense that pays it with the request's ID.

The amount and status have their own columns, and an expense title no longer copies the recipient's name.
"""

import frappe

from churchit.church_finances.doctype.alms_request.alms_request import get_expense_title, get_recipient_name


def execute():
	for request in frappe.get_all(
		"Alms Request", fields=["name", "recipient_type", "recipient", "associated_expense"]
	):
		title = get_recipient_name(request.recipient_type, request.recipient)
		frappe.db.set_value("Alms Request", request.name, "title", title, update_modified=False)
		if request.associated_expense:
			frappe.db.set_value(
				"Expense",
				request.associated_expense,
				"title",
				get_expense_title(request.name),
				update_modified=False,
			)
