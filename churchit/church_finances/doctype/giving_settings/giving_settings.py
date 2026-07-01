# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class GivingSettings(Document):
	def validate(self):
		self.normalize_default_gateway()

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

	def get_offered_gateways(self):
		"""Return the curated gateways as ``[{"name", "label"}]``, default first."""
		ordered = sorted(self.gateways, key=lambda g: 0 if g.is_default else 1)
		return [
			{"name": g.payment_gateway, "label": g.label or g.payment_gateway}
			for g in ordered
		]

	def get_default_gateway(self):
		for g in self.gateways:
			if g.is_default:
				return g.payment_gateway
		return self.gateways[0].payment_gateway if self.gateways else None
