# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qsl, urlencode, urlparse

import frappe
from frappe.utils import add_to_date, flt, fmt_money, now_datetime, set_request
from frappe.website.serve import get_response

from churchit.church_finances.doctype.giving_settings.test_giving_settings import make_gateway
from churchit.church_finances.doctype.online_donation.online_donation import alert_unrecorded_gifts
from churchit.church_finances.doctype.online_donation.test_online_donation import ensure_online_payment_type
from churchit.church_ministries.attendance import record
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	CONFIRMED,
	PAID,
	PAYMENT_DUE_TEMPLATE,
	PENDING,
	REFUND_DUE,
	REFUNDED,
	UNPAID,
	FunctionSignUp,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.www import register
from churchit.www.register import get_payment_link, pay

SIGN_UP = "Function Sign-Up"
PAY_PATH = "/api/method/churchit.www.register.pay"
ADULT = [{"selection": "Adult", "price": 20}]


def log_charge(sign_up, amount, currency="USD"):
	"""The Completed Integration Request a gateway logs for *sign_up*, with what it charged."""
	return frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": "Stripe",
			"reference_doctype": sign_up.doctype,
			"reference_docname": sign_up.name,
			"status": "Completed",
			"data": json.dumps({"amount": amount, "currency": currency}),
		}
	).insert(ignore_permissions=True)


def bind_finance(email, first_name, church):
	user = ensure_user(email, first_name, roles=("Church Finance",))
	make_person(first_name, "Finance", church=church, user=user)
	return user


def alerts(user, record):
	return frappe.get_all(
		"Notification Log", filters={"for_user": user, "document_name": record.name}, pluck="subject"
	)


def collections_of(record):
	"""The Donation rows recorded for *record*, by the name in their notes."""
	return frappe.get_all(
		"Donation",
		filters={"notes": ("like", f"%{record.name}"), "parenttype": "Collection"},
		fields=["parent", "amount", "fund", "person"],
	)


class SignUpPaymentTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_online_payment_type()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.fund_a = ensure(
			"Fund", {"fund": "_Test Fees A"}, {"fund": "_Test Fees A", "church": cls.branch_a}
		)
		cls.fund_b = ensure(
			"Fund", {"fund": "_Test Fees B"}, {"fund": "_Test Fees B", "church": cls.branch_b}
		)
		cls.finance_a = bind_finance("_test_fees_finance_a@example.com", "FeesFinanceA", cls.branch_a)
		cls.finance_b = bind_finance("_test_fees_finance_b@example.com", "FeesFinanceB", cls.branch_b)
		cls.people = [make_person("_Test Fees", name, church=cls.branch_a).name for name in ("Ann", "Ben")]

		cls.gateway = make_gateway("_Test Fees Gateway")
		settings = frappe.get_doc("Giving Settings")
		settings.currency = "USD"
		settings.gateways = []
		settings.append("gateways", {"payment_gateway": cls.gateway})
		settings.save(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		email = patch.object(FunctionSignUp, "send_registrant_email")
		self.send_registrant_email = email.start()
		self.addCleanup(email.stop)

	def make_function(self, church=None, **values):
		values = {
			"church": church or self.branch_a,
			"sign_up_fund": self.fund_a,
			"selections": ADULT,
			**values,
		}
		return make_function("_Test Fees Camp", allow_sign_ups=1, **values).name

	def sign_up(self, function, person=None):
		person = person or self.people[0]
		return make_sign_up(function, person, attendees=[{"person": person, "selection": "Adult"}])

	def payment_emails(self):
		return [
			call for call in self.send_registrant_email.call_args_list if call.args[0] == PAYMENT_DUE_TEMPLATE
		]


class TestSignUpFund(SignUpPaymentTestCase):
	def test_a_price_needs_a_sign_up_fund(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Sign-Up Fund"):
			self.make_function(sign_up_fund=None)

	def test_the_fund_belongs_to_the_payment_church_or_is_shared(self):
		shared_fund = ensure(
			"Fund", {"fund": "_Test Fees Shared"}, {"fund": "_Test Fees Shared", "is_shared": 1}
		)
		self.make_function(sign_up_fund=shared_fund)
		with self.assertRaises(frappe.PermissionError):
			self.make_function(sign_up_fund=self.fund_b)

	def test_a_shared_function_takes_a_fund_of_the_church_that_shared_it(self):
		function = self.make_function(is_shared=1)
		self.assertEqual(
			frappe.db.get_value("Function", function, ["church", "shared_by_church"]), ("", self.branch_a)
		)
		with self.assertRaises(frappe.PermissionError):
			self.make_function(is_shared=1, sign_up_fund=self.fund_b)

	def test_an_attendance_save_keeps_a_fund_that_was_unshared(self):
		shared_fund = ensure(
			"Fund", {"fund": "_Test Fees Unshared"}, {"fund": "_Test Fees Unshared", "is_shared": 1}
		)
		function = self.make_function(sign_up_fund=shared_fund)
		# Church B, which owns the fund, stops sharing it.
		frappe.db.set_value("Fund", shared_fund, {"is_shared": 0, "church": self.branch_b})

		self.assertTrue(record(self.people[0], function, "Checked-In"))


class TestPayLink(SignUpPaymentTestCase):
	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		frappe.local.response = frappe._dict(docs=[])
		frappe.local.request = frappe.local.request_ip = None
		super().tearDown()

	def open_link(self, url, sign_up=None):
		"""Open the signed pay *url* as a guest, with *sign_up* put in place of the signed one."""
		query = urlparse(url).query
		params = dict(parse_qsl(query))
		if sign_up:
			query = query.replace(f"sign_up={params['sign_up']}", f"sign_up={sign_up}")
			params["sign_up"] = sign_up
		set_request(method="GET", path=PAY_PATH, query_string=query)
		frappe.local.request_ip = "127.0.0.1"
		frappe.local.form_dict = frappe._dict(params)
		controller = MagicMock()
		controller.get_payment_url.return_value = "https://pay.example.com/checkout"
		frappe.set_user("Guest")
		try:
			with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
				pay(**params)
		finally:
			frappe.set_user("Administrator")
		return controller

	def test_a_held_sign_up_gets_a_signed_link_to_the_checkout_of_its_amount_due(self):
		sign_up = self.sign_up(self.make_function())
		self.assertEqual((sign_up.status, sign_up.amount_due), (PENDING, 20))

		url = get_payment_link(sign_up)["pay_url"]
		controller = self.open_link(url)

		self.assertEqual(frappe.local.response.location, "https://pay.example.com/checkout")
		checkout = controller.get_payment_url.call_args.kwargs
		self.assertEqual(
			(checkout["amount"], checkout["currency"], checkout["reference_docname"]),
			(20, "USD", sign_up.name),
		)
		# stripe_checkout refuses a URL without the gateway.
		self.assertEqual(checkout["payment_gateway"], self.gateway)

	def test_the_link_shows_the_amount_due_and_the_discount(self):
		function = self.make_function(discounts=[{"kind": "Code", "code": "SAVE5", "amount": 5}])
		person = self.people[0]
		sign_up = make_sign_up(
			function, person, attendees=[{"person": person, "selection": "Adult"}], discount_code="save5"
		)

		link = get_payment_link(sign_up)
		self.assertEqual(
			(link["amount_due"], link["discount"]),
			(fmt_money(15, currency="USD"), fmt_money(5, currency="USD")),
		)
		self.assertNotIn("discount", get_payment_link(self.sign_up(self.make_function(), self.people[1])))

	def test_a_link_with_a_changed_sign_up_is_refused(self):
		function = self.make_function()
		url = get_payment_link(self.sign_up(function))["pay_url"]
		other = self.sign_up(function, self.people[1])

		controller = self.open_link(url, sign_up=other.name)

		controller.get_payment_url.assert_not_called()
		self.assertNotEqual(frappe.local.response.get("type"), "redirect")

	def test_no_link_without_an_amount_due_or_an_offered_gateway(self):
		free = make_sign_up(self.make_function(selections=[]), self.people[0])
		self.assertEqual((free.status, get_payment_link(free)), (CONFIRMED, {}))

		held = self.sign_up(self.make_function())
		settings = frappe.get_doc("Giving Settings")
		settings.gateways = []
		settings.save(ignore_permissions=True)
		self.assertEqual(get_payment_link(held), {})


class TestPaymentRequest(SignUpPaymentTestCase):
	def test_a_new_hold_sends_one_payment_email_with_the_link(self):
		sign_up = self.sign_up(self.make_function())

		self.assertEqual(len(self.payment_emails()), 1)
		context = self.payment_emails()[0].kwargs["context"]
		self.assertEqual(context["pay_url"], sign_up.pay_url)
		self.assertIn("20", context["amount"])

		sign_up.notes = "_Test edit"
		sign_up.save(ignore_permissions=True)
		self.assertEqual(len(self.payment_emails()), 1)

	def test_an_approved_sign_up_with_an_amount_due_gets_one_payment_email(self):
		editor = ensure_user("_test_fees_editor@example.com", "FeesEditor", roles=("Church People Editor",))
		make_person("_Test Fees", "Editor", church=self.branch_a, user=editor)
		sign_up = self.sign_up(self.make_function(sign_up_requires_approval=1))
		self.assertEqual(self.payment_emails(), [])

		frappe.set_user(editor)
		frappe.get_doc(SIGN_UP, sign_up.name).approve()
		frappe.set_user("Administrator")

		self.assertEqual(len(self.payment_emails()), 1)

	def test_the_template_shows_the_link_or_asks_for_payment_at_the_office(self):
		folder = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))
		values = json.loads(
			(folder / "sign_up_payment_due_template/sign_up_payment_due_template.json").read_text()
		)
		template = frappe.get_doc(values)
		context = {"first_name": "Ann", "function_name": "Camp", "date": "1 May", "amount": "$20.00"}

		email = template.get_formatted_email({**context, "pay_url": "https://example.com/pay"})
		self.assertIn('href="https://example.com/pay"', email["message"])
		self.assertIn("Camp", email["subject"])
		self.assertIn("church office", template.get_formatted_email({**context, "pay_url": ""})["message"])

		# A guest types the name that gives first_name, so markup in it is shown as text.
		link = '<a href="https://evil.example">Pay here</a>'
		email = template.get_formatted_email({**context, "first_name": link, "function_name": link})
		message = email["message"]
		self.assertNotIn(link, message)
		self.assertIn("Dear &lt;a href=", message)
		self.assertIn("<strong>&lt;a href=", message)


class TestPaymentCallback(SignUpPaymentTestCase):
	def test_a_matching_charge_records_one_collection_and_confirms_the_sign_up(self):
		sign_up = self.sign_up(self.make_function())
		log_charge(sign_up, 20)

		# The gateway calls back in the payer's session, a guest's here.
		frappe.set_user("Guest")
		sign_up.on_payment_authorized("Completed")
		frappe.set_user("Administrator")
		sign_up.reload()

		self.assertEqual((sign_up.status, sign_up.payment_status, sign_up.amount_paid), (CONFIRMED, PAID, 20))
		attendance = frappe.get_doc("Function", sign_up.function).attendance
		self.assertEqual([row.person for row in attendance], [self.people[0]])
		rows = collections_of(sign_up)
		self.assertEqual([(row.amount, row.fund) for row in rows], [(20, self.fund_a)])
		# A row with no person is on no Giving Statement.
		self.assertIsNone(rows[0].person)
		collection = frappe.get_doc("Collection", rows[0].parent)
		self.assertEqual((collection.church, collection.docstatus), (self.branch_a, 1))

		self.assertEqual(alerts(self.finance_a, sign_up), [])

	def test_a_charge_after_an_offline_payment_records_nothing_and_alerts_finance(self):
		sign_up = self.sign_up(self.make_function())
		frappe.set_user(self.finance_a)
		frappe.get_doc(SIGN_UP, sign_up.name).record_offline_payment()
		frappe.set_user("Administrator")

		# The checkout page the registrant opened before still takes the card.
		log_charge(sign_up, 20)
		frappe.get_doc(SIGN_UP, sign_up.name).on_payment_authorized("Completed")

		self.assertEqual(frappe.db.get_value(SIGN_UP, sign_up.name, "payment_status"), PAID)
		self.assertEqual(collections_of(sign_up), [])
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)
		self.assertIn("charged again", alerts(self.finance_a, sign_up)[0])
		self.assertEqual(alerts(self.finance_b, sign_up), [])

	def test_a_second_callback_for_one_charge_adds_nothing(self):
		sign_up = self.sign_up(self.make_function())
		log_charge(sign_up, 20)

		frappe.get_doc(SIGN_UP, sign_up.name).on_payment_authorized("Completed")
		frappe.get_doc(SIGN_UP, sign_up.name).on_payment_authorized("Completed")

		self.assertEqual(
			frappe.db.get_value(SIGN_UP, sign_up.name, ["payment_status", "amount_paid"]), (PAID, 20)
		)
		self.assertEqual(len(collections_of(sign_up)), 1)
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)

	def test_a_shared_function_records_at_the_church_that_shared_it(self):
		sign_up = self.sign_up(self.make_function(is_shared=1))
		self.assertEqual(sign_up.church, "")
		log_charge(sign_up, 20)

		sign_up.on_payment_authorized("Completed")

		collection = collections_of(sign_up)[0].parent
		self.assertEqual(frappe.db.get_value("Collection", collection, "church"), self.branch_a)

	def test_a_smaller_charge_records_nothing_and_alerts_the_payment_churchs_finance(self):
		sign_up = self.sign_up(self.make_function())
		log_charge(sign_up, 5)

		sign_up.on_payment_authorized("Completed")
		sign_up.reload()

		self.assertEqual((sign_up.status, sign_up.payment_status, sign_up.amount_paid), (PENDING, UNPAID, 0))
		self.assertEqual(collections_of(sign_up), [])
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)
		self.assertEqual(alerts(self.finance_b, sign_up), [])

	def test_a_late_payment_takes_a_free_seat(self):
		sign_up = self.sign_up(self.make_function(capacity=1))
		past = add_to_date(now_datetime(), hours=-1)
		frappe.db.set_value(SIGN_UP, sign_up.name, {"status": CANCELLED, "hold_expires_on": past})
		log_charge(sign_up, 20)

		frappe.get_doc(SIGN_UP, sign_up.name).on_payment_authorized("Completed")

		self.assertEqual(
			frappe.db.get_value(SIGN_UP, sign_up.name, ["status", "payment_status"]), (CONFIRMED, PAID)
		)

	def test_a_late_payment_with_no_free_seat_is_refund_due(self):
		function = self.make_function(capacity=1)
		sign_up = self.sign_up(function)
		past = add_to_date(now_datetime(), hours=-1)
		frappe.db.set_value(SIGN_UP, sign_up.name, {"status": CANCELLED, "hold_expires_on": past})
		self.assertEqual(self.sign_up(function, self.people[1]).status, PENDING)
		log_charge(sign_up, 20)

		frappe.get_doc(SIGN_UP, sign_up.name).on_payment_authorized("Completed")

		self.assertEqual(
			frappe.db.get_value(SIGN_UP, sign_up.name, ["status", "payment_status"]), (CANCELLED, REFUND_DUE)
		)
		self.assertEqual(len(collections_of(sign_up)), 1)

	def test_the_daily_alert_reports_an_unpaid_sign_up_with_a_completed_charge(self):
		sign_up = self.sign_up(self.make_function())
		log_charge(sign_up, 20)

		alert_unrecorded_gifts()
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)
		self.assertEqual(alerts(self.finance_b, sign_up), [])

		sign_up.on_payment_authorized("Completed")
		alert_unrecorded_gifts()
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)


class TestPaymentByHand(SignUpPaymentTestCase):
	def call_as(self, user, method, sign_up):
		frappe.set_user(user)
		try:
			getattr(frappe.get_doc(SIGN_UP, sign_up.name), method)()
		finally:
			frappe.set_user("Administrator")
		sign_up.reload()

	def test_finance_records_an_offline_payment_with_no_collection(self):
		sign_up = self.sign_up(self.make_function())

		self.call_as(self.finance_a, "record_offline_payment", sign_up)

		self.assertEqual((sign_up.status, sign_up.payment_status, sign_up.amount_paid), (CONFIRMED, PAID, 20))
		self.assertEqual(collections_of(sign_up), [])
		with self.assertRaises(frappe.ValidationError):
			self.call_as(self.finance_a, "record_offline_payment", sign_up)

	def test_finance_records_a_refund(self):
		sign_up = self.sign_up(self.make_function())
		with self.assertRaises(frappe.ValidationError):
			self.call_as(self.finance_a, "record_refund", sign_up)

		self.call_as(self.finance_a, "record_offline_payment", sign_up)
		self.call_as(self.finance_a, "record_refund", sign_up)

		self.assertEqual((sign_up.status, sign_up.payment_status), (CONFIRMED, REFUNDED))

	def test_the_registrant_cannot_record_their_own_payment_or_refund(self):
		member = ensure_user("_test_fees_member@example.com", "FeesMember")
		person = make_person("_Test Fees", "Member", church=self.branch_a, user=member).name
		function = self.make_function()
		frappe.set_user(member)
		mine = frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": function,
				"attendees": [{"person": person, "selection": "Adult"}],
			}
		).insert()
		mine.check_permission("write")
		frappe.set_user("Administrator")

		for method in ("record_offline_payment", "record_refund"):
			with self.assertRaises(frappe.PermissionError):
				self.call_as(member, method, mine)
		self.assertEqual((mine.payment_status, flt(mine.amount_paid)), (UNPAID, 0))

	def test_another_churchs_finance_cannot_record_a_payment(self):
		sign_up = self.sign_up(self.make_function())

		with self.assertRaises(frappe.PermissionError):
			self.call_as(self.finance_b, "record_offline_payment", sign_up)
		self.assertEqual(sign_up.payment_status, UNPAID)


class TestPaidSignUpCancel(SignUpPaymentTestCase):
	"""A paid sign-up that ends keeps its record, so Finance knows a refund is due."""

	def paid_sign_up(self, **values):
		sign_up = self.sign_up(self.make_function(**values))
		frappe.set_user(self.finance_a)
		try:
			frappe.get_doc(SIGN_UP, sign_up.name).record_offline_payment()
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc(SIGN_UP, sign_up.name)

	def test_a_cancelled_paid_sign_up_is_refund_due_and_alerts_finance(self):
		sign_up = self.paid_sign_up()

		sign_up.cancel_registration()

		self.assertEqual(
			frappe.db.get_value(SIGN_UP, sign_up.name, ["status", "payment_status"]), (CANCELLED, REFUND_DUE)
		)
		self.assertEqual(len(alerts(self.finance_a, sign_up)), 1)
		self.assertEqual(alerts(self.finance_b, sign_up), [])

	def test_a_declined_paid_sign_up_is_refund_due(self):
		sign_up = self.paid_sign_up(sign_up_requires_approval=1)
		self.assertEqual((sign_up.status, sign_up.payment_status), (PENDING, PAID))

		sign_up.decline()

		self.assertEqual(
			frappe.db.get_value(SIGN_UP, sign_up.name, ["status", "payment_status"]), (CANCELLED, REFUND_DUE)
		)

	def test_the_registrant_cannot_delete_a_paid_sign_up(self):
		member = ensure_user("_test_fees_deleter@example.com", "FeesDeleter")
		make_person("_Test Fees", "Deleter", church=self.branch_a, user=member)
		manager = ensure_user("_test_fees_manager@example.com", "FeesManager", roles=("Church Manager",))
		make_person("_Test Fees", "Manager", church=self.branch_a, user=manager)
		sign_up = self.paid_sign_up()
		frappe.db.set_value(SIGN_UP, sign_up.name, "owner", member)

		frappe.set_user(member)
		try:
			with self.assertRaisesRegex(frappe.PermissionError, "paid"):
				frappe.delete_doc(SIGN_UP, sign_up.name)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists(SIGN_UP, sign_up.name))

		frappe.set_user(manager)
		try:
			frappe.delete_doc(SIGN_UP, sign_up.name)
		finally:
			frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(SIGN_UP, sign_up.name))


class TestRegisterDiscountCode(SignUpPaymentTestCase):
	"""The /register page takes a discount code and never shows one."""

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Church", self.branch_a, "publish", 1)
		self.function = self.make_function(
			publish=1,
			allow_guest_sign_ups=1,
			selections=[],
			discounts=[
				{"kind": "Code", "code": "_TESTSECRET", "amount": 5},
				{"kind": "Code", "code": "_TESTOTHER", "amount": 5},
			],
		)
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		frappe.local.request = None
		super().tearDown()

	def test_the_form_asks_for_a_code_and_names_none(self):
		frappe.set_user("Guest")
		query = {"church": self.branch_a, "function": self.function}
		set_request(method="GET", path="register", query_string=urlencode(query))
		frappe.local.form_dict = frappe._dict(query)
		html = get_response("register").get_data(as_text=True)

		self.assertIn('name="discount_code"', html)
		self.assertNotIn("_TESTSECRET", html)
		self.assertNotIn("_TESTOTHER", html)

	def test_the_sign_up_keeps_the_typed_code_and_the_response_names_no_code(self):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.branch_a)
		response = frappe.as_json(
			register.sign_up(
				self.function, "_Test Dora Discount", "_test_dora@example.com", discount_code="_testsecret"
			)
		)
		frappe.set_user("Administrator")

		self.assertNotIn("_TESTSECRET", response.upper())
		self.assertNotIn("_TESTOTHER", response)
		stored = frappe.get_doc(
			SIGN_UP, {"function": self.function, "registrant_name": "_Test Dora Discount"}
		)
		self.assertEqual(stored.discount_code, "_testsecret")
