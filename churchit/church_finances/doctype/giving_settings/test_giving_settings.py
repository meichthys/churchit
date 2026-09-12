# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


class TestGivingSettings(FrappeTestCase):
	"""Gateway normalisation works on the in-memory Single, so nothing is saved."""

	def _settings(self, *gateways):
		settings = frappe.new_doc("Giving Settings")
		for name, is_default in gateways:
			settings.append("gateways", {"payment_gateway": name, "is_default": is_default})
		return settings

	def test_first_gateway_becomes_default_when_none_is_marked(self):
		settings = self._settings(("Stripe", 0), ("PayPal", 0))
		settings.normalize_default_gateway()
		self.assertEqual([g.is_default for g in settings.gateways], [1, 0])
		self.assertEqual(settings.get_default_gateway(), "Stripe")

	def test_multiple_defaults_are_rejected(self):
		with self.assertRaises(ValidationError):
			self._settings(("Stripe", 1), ("PayPal", 1)).normalize_default_gateway()

	def test_no_gateways_is_fine(self):
		settings = self._settings()
		settings.normalize_default_gateway()
		self.assertEqual(settings.get_offered_gateways(), [])
		self.assertIsNone(settings.get_default_gateway())

	def test_offered_gateways_put_the_default_first_with_label_fallback(self):
		settings = self._settings(("PayPal", 0), ("Stripe", 1))
		settings.gateways[0].label = "Pay with PayPal"
		self.assertEqual(
			settings.get_offered_gateways(),
			[{"name": "Stripe", "label": "Stripe"}, {"name": "PayPal", "label": "Pay with PayPal"}],
		)
