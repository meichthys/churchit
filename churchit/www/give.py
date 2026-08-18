# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, get_fullname, get_url

from churchit.contacts import get_primary_email

no_cache = 1


def get_context(context):
	settings = frappe.get_cached_doc("Giving Settings")
	context.no_cache = 1
	context.title = _("Give")
	context.enabled = bool(settings.enabled)
	context.currency = settings.currency or "USD"
	context.thank_you_message = settings.thank_you_message
	context.success = frappe.form_dict.get("success")

	# When anonymous giving is off, the giver must log in so the gift links to a Person.
	if settings.enabled and not settings.allow_anonymous and frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/give"
		raise frappe.Redirect

	# Funds the giver can choose from (name = link value, fund = display label).
	# Only funds explicitly opted in via "Allow giving to this fund" are offered.
	context.funds = frappe.get_all(
		"Fund", filters={"allow_giving": 1}, fields=["name", "fund"], order_by="fund"
	)
	context.default_fund = settings.default_fund

	# Gateways the donor may choose from. With one gateway the page hides the
	# picker and uses it silently; with several the donor selects one.
	context.gateways = settings.get_offered_gateways()
	context.default_gateway = settings.get_default_gateway()

	# Prefill the giver's details from their linked Person when logged in.
	context.is_logged_in = frappe.session.user != "Guest"
	context.donor_name = ""
	context.donor_email = ""
	if context.is_logged_in:
		person = frappe.db.get_value(
			"Person", {"user": frappe.session.user}, ["name", "full_name"], as_dict=True
		)
		if person:
			context.donor_name = person.full_name or ""
			context.donor_email = get_primary_email("Person", person.name) or ""
		if not context.donor_name:
			context.donor_name = get_fullname(frappe.session.user)
		if not context.donor_email:
			context.donor_email = frappe.db.get_value("User", frappe.session.user, "email") or ""


@frappe.whitelist(allow_guest=True)
def start_donation(amount, fund, payment_gateway=None, donor_name=None, email=None, notes=None):
	"""Create a pending Online Donation and return the payment-gateway URL the
	browser should redirect to. The gateway calls back into
	``OnlineDonation.on_payment_authorized`` once the donor pays."""
	settings = frappe.get_cached_doc("Giving Settings")
	if not settings.enabled:
		frappe.throw(_("Online giving is currently unavailable."))

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Please enter an amount greater than zero."))

	if not fund or not frappe.db.get_value("Fund", fund, "allow_giving"):
		frappe.throw(_("Please choose a valid fund."))

	# Resolve the gateway from the donor's choice, but only honour values that
	# are actually offered — never trust a client-supplied gateway blindly.
	offered = {g["name"] for g in settings.get_offered_gateways()}
	if not offered:
		frappe.throw(_("No payment gateway is configured. Please contact the church office."))
	if payment_gateway and payment_gateway not in offered:
		frappe.throw(_("Please choose a valid payment method."))
	payment_gateway = payment_gateway or settings.get_default_gateway()

	# Resolve the giver's Person from the session — never trust a client-supplied person.
	person = None
	if frappe.session.user != "Guest":
		person = frappe.db.get_value("Person", {"user": frappe.session.user}, "name")

	if not person:
		if not settings.allow_anonymous:
			frappe.throw(_("Please log in to give."))
		if not (donor_name and email):
			frappe.throw(_("Please provide your name and email."))

	currency = settings.currency or "USD"
	gift = frappe.get_doc(
		{
			"doctype": "Online Donation",
			"amount": amount,
			"fund": fund,
			"person": person,
			"donor_name": donor_name,
			"email": email,
			"notes": notes,
			"currency": currency,
			"payment_gateway": payment_gateway,
			"status": "Pending",
		}
	).insert(ignore_permissions=True)

	from payments.utils import get_payment_gateway_controller

	controller = get_payment_gateway_controller(payment_gateway)
	if hasattr(controller, "validate_transaction_currency"):
		controller.validate_transaction_currency(currency)

	payer_email = email or (None if frappe.session.user == "Guest" else frappe.session.user)
	payer_name = donor_name or (
		None if frappe.session.user == "Guest" else get_fullname(frappe.session.user)
	)

	return controller.get_payment_url(
		**{
			"amount": amount,
			"title": _("Church Donation"),
			"description": _("Online gift to the {0} fund").format(
				frappe.db.get_value("Fund", fund, "fund") or fund
			),
			"reference_doctype": "Online Donation",
			"reference_docname": gift.name,
			"payer_email": payer_email,
			"payer_name": payer_name,
			"order_id": gift.name,
			"currency": currency,
			"redirect_to": get_url(f"/give?success={gift.name}"),
		}
	)
