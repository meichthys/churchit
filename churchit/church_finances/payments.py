# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Payments for any record with a church, through the payments app's gateways.

A payable doctype gets its checkout URL from `get_payment_url`. The gateway calls back the record's
``on_payment_authorized(status)``, which locks its row, records the payment once when `is_charge_confirmed`,
and else calls `notify_finance`. The checkout takes the amount from the browser, so only the gateway's
Integration Request proves what the payer paid.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.model.meta import get_field_precision
from frappe.utils import flt, get_fullname, get_url
from frappe.utils.user import get_users_with_role

from churchit.church_communications.scoped_notification import drop_out_of_scope

# The roles that record a payment or a refund by hand. A registrant holds write on their own record.
PAYMENT_RECORDERS = ("Church Finance", "Church Manager")


def get_payment_url(
	reference: Document,
	amount: float,
	currency: str,
	church: str | None,
	title: str,
	description: str,
	payment_gateway: str | None = None,
	payer_name: str | None = None,
	payer_email: str | None = None,
	redirect_to: str | None = None,
) -> str:
	"""The checkout URL of *payment_gateway* when *church* offers it, else of its default gateway."""
	from payments.utils import get_payment_gateway_controller

	gateway = frappe.get_cached_doc("Giving Settings").get_gateway(church, payment_gateway)
	controller = get_payment_gateway_controller(gateway.payment_gateway)
	if hasattr(controller, "validate_transaction_currency"):
		controller.validate_transaction_currency(currency)

	signed_in = frappe.session.user != "Guest"
	checkout = {
		"amount": amount,
		"title": title,
		"description": description,
		"reference_doctype": reference.doctype,
		"reference_docname": reference.name,
		"payer_email": payer_email or (frappe.session.user if signed_in else None),
		"payer_name": payer_name or (get_fullname(frappe.session.user) if signed_in else None),
		"order_id": reference.name,
		"currency": currency,
		"payment_gateway": gateway.payment_gateway,  # stripe_checkout refuses a URL without it
	}
	# Stripe puts every value into its checkout URL, so a missing one would arrive as "None".
	if redirect_to:
		checkout["redirect_to"] = get_url(redirect_to)
	return controller.get_payment_url(**checkout)


def get_fee_to_cover(gateway, amount: float) -> float:
	"""The fee that leaves *amount* after *gateway* (a Giving Gateway row) takes its card rate from the total."""
	return (amount + flt(gateway.fee_fixed)) / (1 - flt(gateway.fee_percent) / 100) - amount


def get_integration_request(reference: Document) -> dict | None:
	"""The newest Completed Integration Request a gateway logged for *reference*."""
	return frappe.db.get_value(
		"Integration Request",
		{"reference_doctype": reference.doctype, "reference_docname": reference.name, "status": "Completed"},
		["name", "data"],
		as_dict=True,
		order_by="creation desc",
	)


def is_charge_confirmed(reference: Document, amount: float, currency: str) -> bool:
	"""True when the gateway charged exactly *amount* in *currency* for *reference*."""
	request = get_integration_request(reference)
	if not request:
		return False

	charged = frappe.parse_json(request.data or "{}")
	precision = get_field_precision(frappe._dict(fieldtype="Currency"), currency=currency)
	return charged.get("currency") == currency and flt(charged.get("amount"), precision) == flt(
		amount, precision
	)


def notify_finance(references: list, reason: str):
	"""Alert the Church Finance users who can see the church of *references* (all of one doctype and church)."""
	users = drop_out_of_scope(get_users_with_role("Church Finance"), references[0], "name")
	if not users:
		return

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"subject": reason,
			"document_type": references[0].doctype,
			"document_name": references[0].name,
		},
	)
