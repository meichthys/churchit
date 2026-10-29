# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

# Gateways whose checkout takes an Online Donation and whose callback reaches on_payment_authorized.
# Braintree is not here: its checkout loads the reference as a Payment Request.
SUPPORTED_GATEWAY_SETTINGS = ("Stripe Settings", "PayPal Settings")


def is_supported_gateway(payment_gateway: str) -> bool:
	settings = frappe.get_cached_value("Payment Gateway", payment_gateway, "gateway_settings")
	return settings in SUPPORTED_GATEWAY_SETTINGS


class GivingSettings(Document):
	def validate(self):
		self.refuse_unsupported_gateways()
		self.refuse_bad_fee_rates()
		self.normalize_default_gateway()

	def refuse_unsupported_gateways(self):
		for row in self.gateways:
			if not is_supported_gateway(row.payment_gateway):
				frappe.throw(
					_("Row {0}: {1} cannot take gifts. Online giving works with Stripe and PayPal.").format(
						row.idx, frappe.bold(row.payment_gateway)
					)
				)

	def refuse_bad_fee_rates(self):
		"""The covered fee divides by (1 - fee percent), so a rate of 100 or more has no fee."""
		for row in self.gateways:
			if not row.offer_fee_cover:
				continue
			if not 0 <= flt(row.fee_percent) < 100:
				frappe.throw(
					_("Row {0}: the fee percent must be at least 0 and less than 100.").format(row.idx)
				)
			if flt(row.fee_fixed) < 0:
				frappe.throw(_("Row {0}: the fixed fee cannot be less than 0.").format(row.idx))

	def normalize_default_gateway(self):
		"""Keep at most one default gateway, and ensure one is chosen when any
		gateways are configured (so the /give page always has a default)."""
		if not self.gateways:
			return

		defaults = [g for g in self.gateways if g.is_default]
		if len(defaults) > 1:
			frappe.throw(_("Only one payment gateway can be marked as the default."))
		if not defaults:
			self.gateways[0].is_default = 1

	def gateways_for(self, church=None):
		"""The gateway rows serving *church*, default first.

		A row naming a church serves only that church, so each congregation's
		gifts reach its own merchant account. A row leaving it blank serves every
		church, which is what a single-church site has and what an organisation
		with one account keeps.
		"""
		rows = [row for row in self.gateways if not row.church or row.church == church]
		# A church with its own gateways uses only those, even when none of them is supported;
		# otherwise the shared ones stand in.
		own = [row for row in rows if row.church]
		supported = [row for row in own or rows if is_supported_gateway(row.payment_gateway)]
		return sorted(supported, key=lambda row: 0 if row.is_default else 1)

	def get_offered_gateways(self, church=None):
		"""Return the gateways offered to *church* as ``[{"name", "label"}]``, default first."""
		return [
			{"name": row.payment_gateway, "label": row.label or row.payment_gateway}
			for row in self.gateways_for(church)
		]

	def get_default_gateway(self, church=None):
		offered = self.gateways_for(church)
		return offered[0].payment_gateway if offered else None

	def get_thank_you_message(self, church=None):
		"""This church's thank-you wording, else the site-wide text."""
		return self.wording_for(church).get("thank_you_message") or self.thank_you_message

	def get_statement_acknowledgment(self, church=None):
		"""This church's acknowledgment wording, else the site-wide text."""
		return self.wording_for(church).get("statement_acknowledgment") or self.statement_acknowledgment

	def get_other_ways_to_give(self, church=None):
		"""This church's bank, standing order or mailing details, else the site-wide text."""
		# An attribute read, so the published-field scan of /give badges the field.
		return self.wording_for(church).other_ways_to_give or self.other_ways_to_give

	def wording_for(self, church=None):
		"""The wording row for *church*, or an empty row when it has none."""
		if not church:
			return frappe._dict()
		return next((row for row in self.church_wording if row.church == church), frappe._dict())

	def get_gateway(self, church=None, payment_gateway=None):
		"""The gateway row that takes a payment for *church*: *payment_gateway* when offered, else the default."""
		rows = self.gateways_for(church)
		if not rows:
			frappe.throw(_("No payment gateway is configured. Please contact the church office."))
		if not payment_gateway:
			return rows[0]

		row = next((row for row in rows if row.payment_gateway == payment_gateway), None)
		if not row:
			frappe.throw(_("Please choose a valid payment method."))
		return row
