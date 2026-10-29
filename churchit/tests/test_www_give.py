# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.exceptions import ValidationError
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_finances.doctype.fund.fund import get_give_link
from churchit.church_finances.doctype.giving_settings.test_giving_settings import make_gateway
from churchit.church_finances.doctype.online_donation.test_online_donation import (
	ensure_online_payment_type,
	log_charge,
)
from churchit.church_foundations.church_access import set_user_church
from churchit.church_website.published_fields import published_field_map
from churchit.church_website.test_published_fields import routes
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)
from churchit.www.give import get_context, start_donation


class TestGivePage(FrappeTestCase):
	def setUp(self):
		self.gateway = make_gateway("_Test Gateway")
		self.other_gateway = make_gateway("_Test Other Gateway")
		self.fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Giving Fund", "allow_giving": 1}
		).insert(ignore_permissions=True)
		self.closed_fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Closed Fund"}).insert(
			ignore_permissions=True
		)
		self._configure(enabled=1, allow_anonymous=1, gateways=[self.gateway, self.other_gateway])
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _configure(self, gateways=(), **values):
		settings = frappe.get_doc("Giving Settings")
		settings.update(values)
		settings.gateways = []
		for gateway in gateways:
			settings.append(
				"gateways", gateway if isinstance(gateway, dict) else {"payment_gateway": gateway}
			)
		settings.save(ignore_permissions=True)

	def _context(self):
		context = frappe._dict()
		get_context(context)
		return context

	def test_context_offers_giving_funds_and_gateways(self):
		context = self._context()
		self.assertTrue(context.enabled)
		self.assertIn(self.fund.name, [f.name for f in context.funds])
		self.assertNotIn(self.closed_fund.name, [f.name for f in context.funds])
		self.assertEqual([g["name"] for g in context.gateways], [self.gateway, self.other_gateway])
		self.assertEqual(context.default_gateway, self.gateway)

	def test_context_prefills_donor_details_from_the_linked_person(self):
		user = ensure_user("_test_giver@example.com", "_Test Giver")
		person = make_person("_Test Generous", "Giver", user=user)
		person.append("emails", {"email_address": "_test_giving@example.com"})
		person.save(ignore_permissions=True)

		frappe.set_user(user)
		context = self._context()
		self.assertEqual(context.donor_name, "_Test Generous Giver")
		self.assertEqual(context.donor_email, "_test_giving@example.com")

	def test_guests_are_redirected_to_login_when_anonymous_giving_is_off(self):
		self._configure(allow_anonymous=0, gateways=[self.gateway])
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			self._context()
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/give")

	def test_the_login_redirect_keeps_the_give_links_fund_and_amount(self):
		self._configure(allow_anonymous=0, gateways=[self.gateway])
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(fund=self.fund.name, amount="25", other="x")
		with self.assertRaises(frappe.Redirect):
			self._context()

		location = urlparse(frappe.local.flags.redirect_location)
		page = urlparse(parse_qs(location.query)["redirect-to"][0])
		self.assertEqual((location.path, page.path), ("/login", "/give"))
		self.assertEqual(parse_qs(page.query), {"fund": [self.fund.name], "amount": ["25"]})

	def test_start_donation_validates_amount_fund_and_gateway(self):
		with self.assertRaises(ValidationError):
			start_donation(0, self.fund.name, donor_name="A", email="a@example.com")
		with self.assertRaises(ValidationError):
			start_donation(10, self.closed_fund.name, donor_name="A", email="a@example.com")
		with self.assertRaises(ValidationError):
			start_donation(
				10, self.fund.name, payment_gateway="Not Offered", donor_name="A", email="a@example.com"
			)

	def test_an_unsupported_gateway_is_refused_and_not_offered(self):
		mpesa = make_gateway("_Test Mpesa Gateway", "Mpesa Settings")
		with self.assertRaises(ValidationError):
			self._configure(gateways=[self.gateway, mpesa])

		# A row stored before the check is skipped, on the page and when giving.
		frappe.db.set_value("Payment Gateway", self.other_gateway, "gateway_settings", "Mpesa Settings")
		frappe.clear_document_cache("Payment Gateway", self.other_gateway)
		self.assertEqual([g["name"] for g in self._context().gateways], [self.gateway])
		with self.assertRaises(ValidationError):
			start_donation(
				10, self.fund.name, payment_gateway=self.other_gateway, donor_name="A", email="a@example.com"
			)

	def test_start_donation_requires_a_configured_gateway(self):
		self._configure(gateways=[])
		with self.assertRaises(ValidationError):
			start_donation(10, self.fund.name, donor_name="A", email="a@example.com")

	def test_start_donation_is_blocked_when_giving_is_disabled(self):
		self._configure(enabled=0, gateways=[self.gateway])
		with self.assertRaises(ValidationError):
			start_donation(10, self.fund.name, donor_name="A", email="a@example.com")

	def test_anonymous_gifts_need_a_name_and_email(self):
		frappe.set_user("Guest")
		with self.assertRaises(ValidationError):
			start_donation(10, self.fund.name)

	def test_anonymous_gifts_are_refused_when_not_allowed(self):
		self._configure(allow_anonymous=0, gateways=[self.gateway])
		frappe.set_user("Guest")
		with self.assertRaises(ValidationError):
			start_donation(10, self.fund.name, donor_name="A", email="a@example.com")

	def test_start_donation_records_a_pending_gift_and_hands_off_to_the_gateway(self):
		controller = MagicMock()
		controller.get_payment_url.return_value = "https://pay.example.com/checkout"
		with patch("payments.utils.get_payment_gateway_controller", return_value=controller) as resolve:
			url = start_donation(
				"25.50",
				self.fund.name,
				payment_gateway=self.other_gateway,
				donor_name="Anon",
				email="anon@example.com",
			)

		self.assertEqual(url, "https://pay.example.com/checkout")
		resolve.assert_called_once_with(self.other_gateway)
		controller.validate_transaction_currency.assert_called_once_with("USD")

		kwargs = controller.get_payment_url.call_args.kwargs
		gift = frappe.get_doc("Online Donation", kwargs["reference_docname"])
		self.assertEqual(gift.status, "Pending")
		self.assertEqual(gift.amount, 25.5)
		self.assertEqual(gift.payment_gateway, self.other_gateway)
		self.assertEqual(gift.donor_name, "Anon")
		self.assertIsNone(gift.person)
		self.assertEqual(kwargs["amount"], 25.5)
		self.assertEqual(kwargs["payment_gateway"], self.other_gateway)
		self.assertEqual(kwargs["payer_email"], "anon@example.com")
		self.assertIn(f"success={gift.name}", kwargs["redirect_to"])

	def test_start_donation_refuses_a_get(self):
		"""A GET carries no CSRF token, so another site could open pending gifts from a visitor's browser."""
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(
			amount=10, fund=self.fund.name, donor_name="Anon", email="anon@example.com"
		)
		gifts = frappe.db.count("Online Donation")

		controller = MagicMock(spec=["get_payment_url"])
		with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
			with self.assertRaises(frappe.PermissionError):
				execute_cmd("churchit.www.give.start_donation")

		self.assertEqual(frappe.db.count("Online Donation"), gifts)

	def give_with_fee_cover(self, offer_fee_cover):
		"""Give 100 through a gateway charging 2.9% + 0.30, asking to cover the fee and naming a fee of 50."""
		gateway = {"payment_gateway": self.gateway, "fee_percent": 2.9, "fee_fixed": 0.30}
		self._configure(gateways=[{**gateway, "offer_fee_cover": offer_fee_cover}])
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(method="POST")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(
			amount=100,
			fund=self.fund.name,
			donor_name="A",
			email="a@example.com",
			cover_fee="1",
			fee_amount=50,
		)

		controller = MagicMock(spec=["get_payment_url"])
		with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
			execute_cmd("churchit.www.give.start_donation")
		frappe.set_user("Administrator")

		kwargs = controller.get_payment_url.call_args.kwargs
		return kwargs["amount"], frappe.get_doc("Online Donation", kwargs["reference_docname"])

	def test_a_covered_fee_is_worked_out_on_the_server_and_given(self):
		self._configure(gateways=[{"payment_gateway": self.gateway, "offer_fee_cover": 1}])
		self.assertEqual(list(self._context().fee_cover), [self.gateway])

		charged, gift = self.give_with_fee_cover(offer_fee_cover=1)

		self.assertEqual(charged, 103.30)
		self.assertEqual((gift.amount, gift.fee_amount), (100, 3.30))
		ensure_online_payment_type()
		log_charge(gift)
		gift.on_payment_authorized("Completed")
		collection = frappe.get_doc(
			"Collection", frappe.db.get_value("Online Donation", gift.name, "collection")
		)
		self.assertEqual(collection.donations[0].amount, 103.30)

	def test_a_gateway_that_offers_no_fee_cover_adds_no_fee(self):
		charged, gift = self.give_with_fee_cover(offer_fee_cover=0)

		self.assertEqual(charged, 100)
		self.assertFalse(gift.fee_amount)
		self.assertEqual(self._context().fee_cover, {})

	def test_logged_in_gifts_link_the_session_person(self):
		user = ensure_user("_test_linked_giver@example.com", "_Test Linked Giver")
		person = make_person("_Test Linked", "Giver", user=user).name
		frappe.set_user(user)

		controller = MagicMock(spec=["get_payment_url"])
		with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
			start_donation(10, self.fund.name)

		gift = frappe.get_doc(
			"Online Donation", controller.get_payment_url.call_args.kwargs["reference_docname"]
		)
		self.assertEqual(gift.person, person)
		self.assertEqual(gift.payment_gateway, self.gateway)


class TestGivingAtABranch(RollbackEachTest):
	"""A gift belongs to the church whose gateway takes the money."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_b, "publish", 1)
		cls.shared_gateway = make_gateway("_Test Shared Gateway")
		cls.branch_gateway = make_gateway("_Test Branch B Gateway")
		settings = frappe.get_doc("Giving Settings")
		settings.update({"enabled": 1, "allow_anonymous": 1, "gateways": []})
		settings.append("gateways", {"payment_gateway": cls.shared_gateway})
		settings.append("gateways", {"payment_gateway": cls.branch_gateway, "church": cls.branch_b})
		settings.save(ignore_permissions=True)
		cls.branch_fund = ensure(
			"Fund",
			{"fund": "_Test Branch B Fund"},
			{"fund": "_Test Branch B Fund", "allow_giving": 1, "church": cls.branch_b},
		)
		cls.shared_fund = ensure(
			"Fund",
			{"fund": "_Test Shared Giving Fund"},
			{"fund": "_Test Shared Giving Fund", "allow_giving": 1, "is_shared": 1},
		)

	def give(self, fund, user="Guest", **form):
		frappe.set_user(user)
		frappe.local.form_dict = frappe._dict(form)
		controller = MagicMock(spec=["get_payment_url"])
		with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
			start_donation(10, fund, donor_name="Anon", email="anon@example.com")
		return frappe.get_doc(
			"Online Donation", controller.get_payment_url.call_args.kwargs["reference_docname"]
		)

	def test_a_gift_to_a_branch_fund_belongs_to_that_branch(self):
		gift = self.give(self.branch_fund)

		self.assertEqual((gift.church, gift.payment_gateway), (self.branch_b, self.branch_gateway))

	def test_a_branch_whose_own_gateway_is_unsupported_gets_no_shared_gateway(self):
		frappe.db.set_value("Payment Gateway", self.branch_gateway, "gateway_settings", "Mpesa Settings")
		frappe.clear_document_cache("Payment Gateway", self.branch_gateway)
		self.addCleanup(frappe.clear_document_cache, "Payment Gateway", self.branch_gateway)

		with self.assertRaisesRegex(ValidationError, "No payment gateway"):
			self.give(self.branch_fund)

	def test_a_shared_fund_gift_belongs_to_the_branch_whose_page_took_it(self):
		user = ensure_user("_test_branch_a_giver@example.com", "_Test Branch A Giver")
		make_person("_Test Branch A", "Giver", user=user, church=self.branch_a)

		gift = self.give(self.shared_fund, user=user, church=self.branch_b)

		self.assertEqual((gift.church, gift.payment_gateway), (self.branch_b, self.branch_gateway))


class TestGiveLinksAndOtherWays(RollbackEachTest):
	"""A give link preselects its fund and amount, and the page tells each church's givers how else to give."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.branch_a, cls.branch_b):
			frappe.db.set_value("Church", church, "publish", 1)
		settings = frappe.get_doc("Giving Settings")
		settings.update(
			{
				"enabled": 1,
				"allow_anonymous": 1,
				"default_fund": None,
				"other_ways_to_give": "<p>_Test the site's bank details</p>",
				"gateways": [],
				"church_wording": [],
			}
		)
		settings.append("gateways", {"payment_gateway": make_gateway("_Test Link Gateway")})
		settings.append(
			"church_wording",
			{"church": cls.branch_b, "other_ways_to_give": "<p>_Test Branch B bank details</p>"},
		)
		settings.save(ignore_permissions=True)
		cls.fund_b = ensure(
			"Fund",
			{"fund": "_Test Link Fund B"},
			{"fund": "_Test Link Fund B", "allow_giving": 1, "church": cls.branch_b},
		)
		cls.finance = {}
		for key, church in (("a", cls.branch_a), ("b", cls.branch_b)):
			cls.finance[key] = ensure_user(
				f"_test_link_finance_{key}@example.com", f"Finance {key}", roles=("Church Finance",)
			)
			set_user_church(cls.finance[key], church)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def context_for(self, **form):
		frappe.local.form_dict = frappe._dict(form)
		context = frappe._dict()
		get_context(context)
		return context

	def serve_for(self, church, user="Guest"):
		frappe.set_user(user)
		set_request(method="GET", path="give", query_string=f"church={church}")
		frappe.local.form_dict = frappe._dict(church=church)
		return get_response("give").get_data(as_text=True)

	def test_a_give_link_selects_its_fund_and_fills_in_the_amount(self):
		context = self.context_for(church=self.branch_b, fund=self.fund_b, amount="25")

		self.assertEqual(context.default_fund, self.fund_b)
		self.assertEqual(context.amount, 25)

	def test_a_link_to_another_churchs_fund_selects_no_fund(self):
		context = self.context_for(church=self.branch_a, fund=self.fund_b)

		self.assertNotIn(self.fund_b, [fund.name for fund in context.funds])
		self.assertIsNone(context.default_fund)

	def test_a_link_fills_in_only_a_positive_amount(self):
		for amount in ("0", "-5", "abc", ""):
			self.assertIsNone(self.context_for(church=self.branch_b, amount=amount).amount, amount)

	def test_the_give_link_of_a_branch_fund_names_its_church(self):
		frappe.set_user(self.finance["b"])

		link = get_give_link(self.fund_b)

		self.assertTrue(link["url"].endswith(f"/give?church={self.branch_b}&fund={self.fund_b}"), link["url"])
		self.assertTrue(link["qr_code"].startswith("data:image/svg+xml;base64,"))

	def test_a_user_who_cannot_read_the_fund_gets_no_link(self):
		frappe.set_user(self.finance["a"])

		with self.assertRaises(frappe.PermissionError):
			get_give_link(self.fund_b)

	def test_each_church_shows_its_own_other_ways_to_give_also_with_giving_off(self):
		frappe.db.set_single_value("Giving Settings", "enabled", 0)

		branch_b = self.serve_for(self.branch_b)
		self.assertIn("_Test Branch B bank details", branch_b)
		self.assertNotIn("_Test the site's bank details", branch_b)
		self.assertIn("_Test the site's bank details", self.serve_for(self.branch_a))

	def test_a_signed_in_member_sees_their_envelope_number_and_a_guest_sees_none(self):
		user = ensure_user("_test_envelope_giver@example.com", "_Test Envelope")
		make_person("_Test Envelope", "Giver", user=user, church=self.branch_b, envelope_number="123")
		reference = "use your envelope number"

		member_page = self.serve_for(self.branch_b, user=user)
		self.assertIn(reference, member_page)
		self.assertIn("<strong>123</strong>", member_page)
		self.assertNotIn(reference, self.serve_for(self.branch_b))

	def test_the_page_badges_the_fields_it_shows(self):
		published = published_field_map()

		self.assertIn("give", routes(published, "Giving Settings", "other_ways_to_give"))
		self.assertIn("give", routes(published, "Person", "envelope_number"))


class TestGiveLinkInOneChurch(FrappeTestCase):
	def test_a_single_church_link_names_no_church(self):
		force_single_church()
		fund = ensure(
			"Fund",
			{"fund": "_Test Single Church Link Fund"},
			{"fund": "_Test Single Church Link Fund", "allow_giving": 1, "church": ensure_root_church()},
		)

		self.assertTrue(get_give_link(fund)["url"].endswith(f"/give?fund={fund}"))
