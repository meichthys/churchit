# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

NON_CASH = "Non-Cash"


class PaymentType(Document):
	pass


def create_non_cash_payment_type():
	"""Add the Non-Cash Payment Type, unless the site already has a type for donated property."""
	if frappe.db.exists("Payment Type", NON_CASH) or frappe.db.exists("Payment Type", {"is_non_cash": 1}):
		return
	frappe.get_doc(
		{
			"doctype": "Payment Type",
			"type": NON_CASH,
			"is_non_cash": 1,
			"description": "Donated property. Describe it and enter no amount.",
		}
	).insert(ignore_permissions=True)
