# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase


def make_gateway(name, settings="Stripe Settings"):
	"""A Payment Gateway called *name* that runs on the *settings* doctype."""
	gateway = frappe.new_doc("Payment Gateway")
	if frappe.db.exists("Payment Gateway", name):
		gateway = frappe.get_doc("Payment Gateway", name)
	gateway.update({"gateway": name, "gateway_settings": settings})
	return gateway.save(ignore_permissions=True).name


def make_settings(*gateways):
	"""An unsaved Giving Settings with these gateways: (name, is_default[, church])."""
	settings = frappe.new_doc("Giving Settings")
	for name, is_default, *church in gateways:
		make_gateway(name)
		settings.append(
			"gateways",
			{"payment_gateway": name, "is_default": is_default, "church": church[0] if church else None},
		)
	return settings


class TestGivingSettings(FrappeTestCase):
	"""Gateway normalisation works on the in-memory Single, so nothing is saved."""

	def test_first_gateway_becomes_default_when_none_is_marked(self):
		settings = make_settings(("Stripe", 0), ("PayPal", 0))
		settings.normalize_default_gateway()
		self.assertEqual([g.is_default for g in settings.gateways], [1, 0])
		self.assertEqual(settings.get_default_gateway(), "Stripe")

	def test_multiple_defaults_are_rejected(self):
		with self.assertRaises(ValidationError):
			make_settings(("Stripe", 1), ("PayPal", 1)).normalize_default_gateway()

	def test_no_gateways_is_fine(self):
		settings = make_settings()
		settings.normalize_default_gateway()
		self.assertEqual(settings.get_offered_gateways(), [])
		self.assertIsNone(settings.get_default_gateway())

	def test_a_fee_cover_rate_must_leave_a_fee(self):
		"""The /give fee divides by (1 - fee percent), so 100 would fail and more would charge less than the gift."""
		for fee_percent, fee_fixed in ((100, 0), (150, 0), (-1, 0), (2.9, -0.3)):
			settings = make_settings(("Stripe", 1))
			settings.gateways[0].update(
				{"offer_fee_cover": 1, "fee_percent": fee_percent, "fee_fixed": fee_fixed}
			)
			with (
				self.subTest(fee_percent=fee_percent, fee_fixed=fee_fixed),
				self.assertRaises(ValidationError),
			):
				settings.refuse_bad_fee_rates()

		settings.gateways[0].update({"fee_percent": 2.9, "fee_fixed": 0.3})
		settings.refuse_bad_fee_rates()

	def test_offered_gateways_put_the_default_first_with_label_fallback(self):
		settings = make_settings(("PayPal", 0), ("Stripe", 1))
		settings.gateways[0].label = "Pay with PayPal"
		self.assertEqual(
			settings.get_offered_gateways(),
			[{"name": "Stripe", "label": "Stripe"}, {"name": "PayPal", "label": "Pay with PayPal"}],
		)


class TestGivingSettingsPerChurch(FrappeTestCase):
	"""A branch's gifts have to reach its own merchant account, not the main church's."""

	def test_a_church_with_its_own_gateway_uses_only_that(self):
		settings = make_settings(("Shared", 1, None), ("BranchPay", 1, "CHR-BRANCH"))

		self.assertEqual(settings.get_default_gateway("CHR-BRANCH"), "BranchPay")
		self.assertEqual([g["name"] for g in settings.get_offered_gateways("CHR-BRANCH")], ["BranchPay"])

	def test_a_church_without_one_falls_back_to_the_shared_gateways(self):
		settings = make_settings(("Shared", 1, None), ("BranchPay", 1, "CHR-BRANCH"))

		self.assertEqual(settings.get_default_gateway("CHR-OTHER"), "Shared")
		self.assertEqual([g["name"] for g in settings.get_offered_gateways("CHR-OTHER")], ["Shared"])

	def test_asking_for_no_church_offers_only_the_shared_gateways(self):
		"""A single-church site has no church rows, so nothing changes for it."""
		settings = make_settings(("Shared", 1, None))
		self.assertEqual([g["name"] for g in settings.get_offered_gateways()], ["Shared"])

	def test_wording_falls_back_to_the_site_wide_text(self):
		settings = frappe.new_doc("Giving Settings")
		settings.thank_you_message = "Site thanks"
		settings.statement_acknowledgment = "Site wording"
		settings.append("church_wording", {"church": "CHR-BRANCH", "thank_you_message": "Branch thanks"})

		self.assertEqual(settings.get_thank_you_message("CHR-BRANCH"), "Branch thanks")
		self.assertEqual(settings.get_thank_you_message("CHR-OTHER"), "Site thanks")
		# The row fills in only what it sets; the rest still comes from the Single.
		self.assertEqual(settings.get_statement_acknowledgment("CHR-BRANCH"), "Site wording")
		self.assertEqual(settings.get_thank_you_message(), "Site thanks")
