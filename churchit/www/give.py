# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import flt, get_fullname, sbool

from churchit.church_finances.doctype.giving_settings.giving_settings import GivingSettings
from churchit.church_finances.payments import get_fee_to_cover, get_payment_url
from churchit.church_foundations.doctype.church.church import selected_church_name
from churchit.church_scope import church_filters
from churchit.contacts import get_primary_email

no_cache = 1


def get_context(context):
	settings: GivingSettings = frappe.get_cached_doc("Giving Settings")
	church = selected_church_name()
	context.no_cache = 1
	context.title = _("Give")
	context.enabled = bool(settings.enabled)
	context.currency = settings.currency or "USD"
	context.thank_you_message = settings.get_thank_you_message(church)
	context.other_ways_to_give = settings.get_other_ways_to_give(church)
	context.success = frappe.form_dict.get("success")

	# When anonymous giving is off, the giver must log in so the gift links to a Person.
	# The login returns to the give link's church, fund and amount.
	if settings.enabled and not settings.allow_anonymous and frappe.session.user == "Guest":
		link = {
			key: frappe.form_dict[key] for key in ("church", "fund", "amount") if frappe.form_dict.get(key)
		}
		page = "/give?" + urlencode(link) if link else "/give"
		frappe.local.flags.redirect_location = "/login?" + urlencode({"redirect-to": page}, safe="/")
		raise frappe.Redirect

	# Funds the giver can choose from (name = link value, fund = display label).
	# Only funds explicitly opted in via "Allow giving to this fund" are offered.
	context.funds = frappe.get_all(
		"Fund",
		filters=church_filters(church, allow_giving=1),
		fields=["name", "fund"],
		order_by="fund",
	)
	# A give link (?fund=&amount=) chooses only a fund this page offers.
	chosen_fund = frappe.form_dict.get("fund") or settings.default_fund
	context.default_fund = chosen_fund if chosen_fund in {fund.name for fund in context.funds} else None
	amount = flt(frappe.form_dict.get("amount"))
	context.amount = amount if amount > 0 else None

	# Gateways the donor may choose from. With one gateway the page hides the
	# picker and uses it silently; with several the donor selects one.
	context.gateways = settings.get_offered_gateways(church)
	context.default_gateway = settings.get_default_gateway(church)
	context.fee_cover = {
		row.payment_gateway: {"percent": flt(row.fee_percent), "fixed": flt(row.fee_fixed)}
		for row in settings.gateways_for(church)
		if row.offer_fee_cover
	}

	# Prefill the giver's details from their linked Person when logged in.
	context.is_logged_in = frappe.session.user != "Guest"
	context.donor_name = ""
	context.donor_email = ""
	context.envelope_number = None
	if context.is_logged_in:
		person = frappe.db.get_value(
			"Person", {"user": frappe.session.user}, ["name", "full_name", "envelope_number"], as_dict=True
		)
		if person:
			context.donor_name = person.full_name or ""
			context.donor_email = get_primary_email("Person", person.name) or ""
			context.envelope_number = person.envelope_number
		if not context.donor_name:
			context.donor_name = get_fullname(frappe.session.user)
		if not context.donor_email:
			context.donor_email = frappe.db.get_value("User", frappe.session.user, "email") or ""


@frappe.whitelist(allow_guest=True, methods=["POST"])
def start_donation(
	amount: str | float,
	fund: str,
	payment_gateway: str | None = None,
	donor_name: str | None = None,
	email: str | None = None,
	notes: str | None = None,
	cover_fee: str | int = 0,
):
	"""Create a pending Online Donation and return the payment-gateway URL the
	browser should redirect to. The gateway calls back into
	``OnlineDonation.on_payment_authorized`` once the donor pays."""
	settings = frappe.get_cached_doc("Giving Settings")
	if not settings.enabled:
		frappe.throw(_("Online giving is currently unavailable."))

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Please enter an amount greater than zero."))

	# The fund settles which church the gift belongs to, else the page that took it.
	# The gift records that church, so it matches the gateway that takes the money.
	fund_row = frappe.db.get_value("Fund", fund, ["allow_giving", "church"], as_dict=True) if fund else None
	if not fund_row or not fund_row.allow_giving:
		frappe.throw(_("Please choose a valid fund."))
	church = fund_row.church or selected_church_name()

	gateway = settings.get_gateway(church, payment_gateway)

	# Resolve the giver's Person from the session; never trust a client-supplied person.
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
			"church": church,
			"amount": amount,
			"fund": fund,
			"person": person,
			"donor_name": donor_name,
			"email": email,
			"notes": notes,
			"currency": currency,
			"payment_gateway": gateway.payment_gateway,
			"status": "Pending",
		}
	)
	if sbool(cover_fee) and gateway.offer_fee_cover:
		gift.fee_amount = flt(get_fee_to_cover(gateway, amount), gift.precision("fee_amount"))
	gift.insert(ignore_permissions=True)

	return get_payment_url(
		gift,
		gift.charged_amount,
		currency,
		church,
		_("Church Donation"),
		_("Online gift to the {0} fund").format(frappe.db.get_value("Fund", fund, "fund") or fund),
		gift.payment_gateway,
		payer_name=donor_name,
		payer_email=email,
		redirect_to=f"/give?success={gift.name}",
	)
