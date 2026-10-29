# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import MagicMock, patch

import frappe
from frappe.exceptions import ValidationError

from churchit.church_finances.doctype.giving_settings.test_giving_settings import make_gateway
from churchit.church_finances.payments import (
	get_fee_to_cover,
	get_payment_url,
	is_charge_confirmed,
	notify_finance,
)
from churchit.church_operations.doctype.church_task.church_task import ChurchTask
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

STUB_PRICE = 40


class StubPayable(ChurchTask):
	"""A Church Task that takes a payment, the way a sign-up or a form response does."""

	def on_payment_authorized(self, status=None):
		if status != "Completed":
			return
		if frappe.db.get_value(self.doctype, self.name, "status", for_update=True) == "Completed":
			return
		if not is_charge_confirmed(self, STUB_PRICE, "USD"):
			notify_finance([self], f"Task {self.name} was charged the wrong amount.")
			return
		self.db_set("status", "Completed")
		self.add_comment("Comment", "Payment recorded")


def log_charge(reference, amount, currency="USD"):
	return frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": "Stripe",
			"reference_doctype": reference.doctype,
			"reference_docname": reference.name,
			"status": "Completed",
			"data": frappe.as_json({"amount": amount, "currency": currency}),
		}
	).insert(ignore_permissions=True)


class TestPayments(RollbackEachTest):
	"""Any record with a church can take a payment through the payments app."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.finance_a = cls.bind_finance("_test_pay_finance_a@example.com", "PayFinanceA", cls.branch_a)
		cls.finance_b = cls.bind_finance("_test_pay_finance_b@example.com", "PayFinanceB", cls.branch_b)
		cls.shared_gateway = make_gateway("_Test Payments Shared Gateway")
		cls.branch_b_gateway = make_gateway("_Test Payments Branch B Gateway")
		settings = frappe.get_doc("Giving Settings")
		settings.gateways = []
		settings.append("gateways", {"payment_gateway": cls.shared_gateway})
		settings.append("gateways", {"payment_gateway": cls.branch_b_gateway, "church": cls.branch_b})
		settings.save(ignore_permissions=True)

	@classmethod
	def bind_finance(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Finance",))
		make_person(first_name, "Finance", church=church, user=user)
		return user

	def make_task(self):
		return frappe.get_doc(
			{"doctype": "Church Task", "title": "_Test Paid Task", "status": "Open", "church": self.branch_a}
		).insert(ignore_permissions=True)

	def authorize(self, task):
		StubPayable("Church Task", task.name).on_payment_authorized("Completed")

	def alerts(self, user, task):
		return frappe.get_all(
			"Notification Log", filters={"for_user": user, "document_name": task.name}, pluck="document_type"
		)

	def payments_recorded(self, task):
		return frappe.db.count(
			"Comment",
			{"reference_doctype": "Church Task", "reference_name": task.name, "content": "Payment recorded"},
		)

	def test_a_second_callback_records_nothing(self):
		task = self.make_task()
		log_charge(task, "40.00")

		self.authorize(task)
		self.authorize(task)

		self.assertEqual(self.payments_recorded(task), 1)
		self.assertEqual(frappe.db.get_value("Church Task", task.name, "status"), "Completed")

	def test_a_changed_amount_or_currency_records_nothing_and_alerts_the_church(self):
		for amount, currency in ((39, "USD"), (STUB_PRICE, "EUR")):
			task = self.make_task()
			log_charge(task, amount, currency)

			self.authorize(task)

			self.assertEqual(self.payments_recorded(task), 0)
			self.assertEqual(frappe.db.get_value("Church Task", task.name, "status"), "Open")
			self.assertEqual(self.alerts(self.finance_a, task), ["Church Task"])
			self.assertFalse(self.alerts(self.finance_b, task))

	def test_no_completed_charge_is_not_confirmed(self):
		task = self.make_task()

		self.assertFalse(is_charge_confirmed(task, STUB_PRICE, "USD"))

	def test_the_payment_url_names_the_record_and_its_amount(self):
		task = self.make_task()
		controller = MagicMock()
		controller.get_payment_url.return_value = "https://pay.example.com/checkout"

		with patch("payments.utils.get_payment_gateway_controller", return_value=controller) as resolve:
			url = get_payment_url(task, 40, "USD", self.branch_a, "Task", "A paid task", redirect_to="/done")

		self.assertEqual(url, "https://pay.example.com/checkout")
		resolve.assert_called_once_with(self.shared_gateway)
		controller.validate_transaction_currency.assert_called_once_with("USD")
		kwargs = controller.get_payment_url.call_args.kwargs
		self.assertEqual(
			(kwargs["reference_doctype"], kwargs["reference_docname"], kwargs["order_id"]),
			("Church Task", task.name, task.name),
		)
		self.assertEqual((kwargs["amount"], kwargs["currency"]), (40, "USD"))
		self.assertTrue(kwargs["redirect_to"].endswith("/done"))

	def test_a_gateway_the_church_does_not_offer_is_refused(self):
		task = self.make_task()
		controller = MagicMock()

		with patch("payments.utils.get_payment_gateway_controller", return_value=controller):
			with self.assertRaisesRegex(ValidationError, "valid payment method"):
				get_payment_url(task, 40, "USD", self.branch_a, "Task", "A paid task", self.branch_b_gateway)

		controller.get_payment_url.assert_not_called()

	def test_the_fee_to_cover_leaves_the_amount_after_the_card_rate(self):
		gateway = frappe._dict(fee_percent=2.9, fee_fixed=0.30)

		fee = get_fee_to_cover(gateway, 100)

		self.assertAlmostEqual((100 + fee) * (1 - 0.029) - 0.30, 100)
