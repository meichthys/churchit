# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import get_year_ending, get_year_start, nowdate

from churchit.church_finances.doctype.giving_statement.giving_statement import generate_statements
from churchit.church_finances.doctype.online_donation.online_donation import alert_unrecorded_gifts
from churchit.church_people import summaries
from churchit.church_people.summaries.test_serving import queued_people
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


def ensure_online_payment_type():
	# "Online" Payment Type is required for the recorded Collection's Donation row.
	if not frappe.db.exists("Payment Type", "Online"):
		frappe.get_doc({"doctype": "Payment Type", "type": "Online"}).insert(ignore_permissions=True)


def make_gift(fund, amount, **values):
	return frappe.get_doc(
		{"doctype": "Online Donation", "amount": amount, "fund": fund, "currency": "USD", **values}
	).insert(ignore_permissions=True)


def log_charge(gift, amount=None, status="Completed", currency="USD"):
	"""The Integration Request a gateway logs for *gift*, with what it charged."""
	return frappe.get_doc(
		{
			"doctype": "Integration Request",
			"integration_request_service": "Stripe",
			"reference_doctype": "Online Donation",
			"reference_docname": gift.name,
			"status": status,
			"data": frappe.as_json(
				{"amount": gift.charged_amount if amount is None else amount, "currency": currency}
			),
		}
	).insert(ignore_permissions=True)


class TestOnlineDonation(FrappeTestCase):
	def setUp(self):
		ensure_online_payment_type()

	def _make_fund(self):
		return frappe.get_doc({"doctype": "Fund", "fund": "Test Giving Fund"}).insert(ignore_permissions=True)

	def _make_gift(self, fund, amount, **values):
		gift = make_gift(fund.name, amount, **values)
		log_charge(gift)
		return gift

	def test_payment_authorized_records_submitted_collection(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 50, donor_name="Test Giver", email="giver@example.com")

		redirect = gift.on_payment_authorized("Completed")
		gift.reload()

		# The gift is marked paid and points at its Collection
		self.assertEqual(gift.status, "Paid")
		self.assertTrue(gift.collection)
		self.assertIn(f"success={gift.name}", redirect)

		# A submitted, single-row Collection was created with the right donation
		collection = frappe.get_doc("Collection", gift.collection)
		self.assertEqual(collection.docstatus, 1)
		self.assertEqual(len(collection.donations), 1)
		row = collection.donations[0]
		self.assertEqual(row.payment_type, "Online")
		self.assertEqual(row.fund, fund.name)
		self.assertEqual(row.amount, 50)

		# The fund balance increased by the gift amount
		self.assertEqual(frappe.db.get_value("Fund", fund.name, "balance"), 50)

	def test_anonymous_gift_records_without_person(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 25, donor_name="Anon", email="anon@example.com")

		gift.on_payment_authorized("Completed")
		gift.reload()

		self.assertEqual(gift.status, "Paid")
		collection = frappe.get_doc("Collection", gift.collection)
		self.assertFalse(collection.donations[0].person)

	def test_failed_payment_marks_failed(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 10, donor_name="Nope", email="n@example.com")

		gift.on_payment_authorized("Declined")
		gift.reload()

		self.assertEqual(gift.status, "Failed")
		self.assertFalse(gift.collection)

	def test_an_authorized_payment_is_not_a_paid_one(self):
		"""Authorized means the card was held, not charged, so no gift is recorded."""
		fund = self._make_fund()
		gift = self._make_gift(fund, 10, donor_name="Held", email="h@example.com")

		gift.on_payment_authorized("Authorized")
		gift.reload()

		self.assertNotEqual(gift.status, "Paid")
		self.assertFalse(gift.collection)

	def test_authorized_is_idempotent(self):
		fund = self._make_fund()
		gift = self._make_gift(fund, 30, donor_name="Once", email="o@example.com")

		gift.on_payment_authorized("Completed")
		gift.reload()
		first_collection = gift.collection

		# Re-firing the callback must not record a second Collection
		gift.on_payment_authorized("Completed")
		gift.reload()
		self.assertEqual(gift.collection, first_collection)
		self.assertEqual(frappe.db.get_value("Fund", fund.name, "balance"), 30)


class TestChargedGifts(RollbackEachTest):
	"""A gift is recorded only for what the gateway charged, and Finance hears of every other case."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_online_payment_type()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.finance_a = cls.bind_finance("_test_gift_finance_a@example.com", "GiftFinanceA", cls.branch_a)
		cls.finance_b = cls.bind_finance("_test_gift_finance_b@example.com", "GiftFinanceB", cls.branch_b)
		cls.fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Charged Fund", "church": cls.branch_a})
			.insert(ignore_permissions=True)
			.name
		)

	@classmethod
	def bind_finance(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Finance",))
		make_person(first_name, "Finance", church=church, user=user)
		return user

	def alerts(self, user, gift):
		return frappe.get_all(
			"Notification Log", filters={"for_user": user, "document_name": gift.name}, pluck="subject"
		)

	def make_gift(self, amount=100):
		return make_gift(
			self.fund, amount, church=self.branch_a, donor_name="Charged", email="charged@example.com"
		)

	def test_a_charge_below_the_gift_records_nothing(self):
		gift = self.make_gift()
		request = log_charge(gift, amount=1)
		# A newer request that is not Completed does not count.
		log_charge(gift, amount=100, status="Failed")
		collections = frappe.db.count("Collection")

		gift.on_payment_authorized("Completed")
		gift.reload()

		self.assertEqual(gift.status, "Needs Review")
		self.assertFalse(gift.collection)
		self.assertEqual(frappe.db.count("Collection"), collections)
		self.assertEqual(gift.transaction_reference, request.name)
		alerts = self.alerts(self.finance_a, gift)
		self.assertEqual(len(alerts), 1)
		self.assertIn("1.00", alerts[0])
		self.assertIn("100.00", alerts[0])
		self.assertFalse(self.alerts(self.finance_b, gift))

	def test_a_charge_in_another_currency_records_nothing(self):
		gift = self.make_gift()
		log_charge(gift, currency="EUR")

		gift.on_payment_authorized("Completed")

		self.assertEqual(frappe.db.get_value("Online Donation", gift.name, "status"), "Needs Review")

	def test_a_matching_charge_records_the_gift(self):
		gift = self.make_gift()
		request = log_charge(gift, amount="100.00")

		gift.on_payment_authorized("Completed")
		gift.reload()

		self.assertEqual(gift.status, "Paid")
		self.assertEqual(gift.transaction_reference, request.name)
		self.assertTrue(gift.collection)
		self.assertFalse(self.alerts(self.finance_a, gift))

	def test_a_failed_callback_is_reported_and_can_be_recorded(self):
		gift = self.make_gift()
		log_charge(gift)

		alert_unrecorded_gifts()

		self.assertEqual(len(self.alerts(self.finance_a, gift)), 1)
		self.assertFalse(self.alerts(self.finance_b, gift))

		collections = frappe.db.count("Collection")
		frappe.set_user(self.finance_a)
		frappe.get_doc("Online Donation", gift.name).record_charged_gift()
		with self.assertRaisesRegex(frappe.ValidationError, "Only a Pending gift"):
			frappe.get_doc("Online Donation", gift.name).record_charged_gift()
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.count("Collection"), collections + 1)
		self.assertEqual(frappe.db.get_value("Online Donation", gift.name, "status"), "Paid")
		alert_unrecorded_gifts()
		self.assertEqual(len(self.alerts(self.finance_a, gift)), 1)

	def test_another_churchs_finance_cannot_record_a_gift(self):
		gift = self.make_gift()
		log_charge(gift)

		frappe.set_user(self.finance_b)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Online Donation", gift.name).record_charged_gift()
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Online Donation", gift.name, "status"), "Pending")

	def test_only_a_charged_pending_gift_can_be_recorded(self):
		abandoned = self.make_gift()
		cancelled = self.make_gift()
		log_charge(cancelled)
		cancelled.db_set("status", "Cancelled")
		collections = frappe.db.count("Collection")

		frappe.set_user(self.finance_a)
		with self.assertRaisesRegex(frappe.ValidationError, "No completed payment"):
			frappe.get_doc("Online Donation", abandoned.name).record_charged_gift()
		with self.assertRaisesRegex(frappe.ValidationError, "Only a Pending gift"):
			frappe.get_doc("Online Donation", cancelled.name).record_charged_gift()
		frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Online Donation", abandoned.name, "status"), "Pending")
		self.assertEqual(frappe.db.get_value("Online Donation", cancelled.name, "status"), "Cancelled")
		self.assertFalse(self.alerts(self.finance_a, abandoned))
		self.assertEqual(frappe.db.count("Collection"), collections)

	def test_a_covered_fee_is_part_of_the_gift(self):
		gift = make_gift(self.fund, 100, church=self.branch_a, fee_amount=3.30, email="fee@example.com")
		log_charge(gift, amount=103.30)

		gift.on_payment_authorized("Completed")
		gift.reload()

		self.assertEqual(gift.status, "Paid")
		collection = frappe.get_doc("Collection", gift.collection)
		self.assertEqual(collection.donations[0].amount, 103.30)
		self.assertEqual(collection.expected_total, 103.30)

	def test_a_charge_without_the_covered_fee_records_nothing(self):
		gift = make_gift(self.fund, 100, church=self.branch_a, fee_amount=3.30, email="fee@example.com")
		log_charge(gift, amount=100)

		gift.on_payment_authorized("Completed")

		self.assertEqual(frappe.db.get_value("Online Donation", gift.name, "status"), "Needs Review")
		self.assertEqual(len(self.alerts(self.finance_a, gift)), 1)


class TestLinkingAGiftToAPerson(RollbackEachTest):
	"""Finance names the giver of a guest gift, so the gift reaches their statement and giving summary."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_online_payment_type()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.finance = TestChargedGifts.bind_finance(
			"_test_link_finance@example.com", "LinkFinance", cls.branch_a
		)
		cls.staff = ensure_user("_test_link_staff@example.com", "LinkStaff", roles=("Church Staff",))
		make_person("LinkStaff", "Staff", church=cls.branch_a, user=cls.staff)
		cls.fund = (
			frappe.get_doc({"doctype": "Fund", "fund": "_Test Linked Gift Fund", "church": cls.branch_a})
			.insert(ignore_permissions=True)
			.name
		)

	def setUp(self):
		super().setUp()
		person = make_person("_Test Linked", "Giver", church=self.branch_a)
		person.append("emails", {"email_address": "_test_linked_giver@example.com"})
		self.person = person.save(ignore_permissions=True).name

	def paid_guest_gift(self):
		gift = make_gift(self.fund, 40, church=self.branch_a, donor_name="Guest", email="guest@example.com")
		log_charge(gift)
		gift.on_payment_authorized("Completed")
		return frappe.get_doc("Online Donation", gift.name)

	def comments_on(self, collection):
		return frappe.db.count("Comment", {"reference_doctype": "Collection", "reference_name": collection})

	def link(self, gift, user):
		frappe.set_user(user)
		gift = frappe.get_doc("Online Donation", gift.name)
		gift.person = self.person
		queued = queued_people(gift.save)
		frappe.set_user("Administrator")
		return queued

	def test_finance_links_a_paid_guest_gift_to_a_person(self):
		gift = self.paid_guest_gift()
		comments = self.comments_on(gift.collection)

		queued = self.link(gift, self.finance)

		row = frappe.get_all(
			"Donation", filters={"parent": gift.collection}, fields=["person", "person_email"]
		)
		self.assertEqual(row, [{"person": self.person, "person_email": "_test_linked_giver@example.com"}])
		self.assertEqual(self.comments_on(gift.collection), comments + 1)
		comment = frappe.get_last_doc(
			"Comment", filters={"reference_doctype": "Collection", "reference_name": gift.collection}
		)
		self.assertEqual(comment.comment_type, "Info")
		self.assertIn(frappe.db.get_value("Person", self.person, "full_name"), comment.content)
		self.assertNotIn(self.person, comment.content)
		self.assertEqual(queued, [[self.person]])

		summaries.refresh([self.person])
		self.assertTrue(frappe.db.get_value("Person", self.person, "last_gift_on"))
		frappe.set_user(self.finance)
		generate_statements(str(get_year_start(nowdate())), str(get_year_ending(nowdate())))
		frappe.set_user("Administrator")
		statement = frappe.get_all("Giving Statement", filters={"person": self.person}, pluck="total_amount")
		self.assertEqual(statement, [40])

	def test_a_pending_gift_changes_only_its_own_field(self):
		gift = make_gift(self.fund, 40, church=self.branch_a, donor_name="Guest", email="guest@example.com")
		comments = frappe.db.count("Comment", {"reference_doctype": "Collection"})

		queued = self.link(gift, self.finance)

		self.assertEqual(frappe.db.get_value("Online Donation", gift.name, "person"), self.person)
		self.assertEqual(frappe.db.count("Comment", {"reference_doctype": "Collection"}), comments)
		self.assertEqual(queued, [])

	def test_a_gift_cannot_move_to_another_collection(self):
		"""A REST update can send a read only field, and a new person would rewrite that Collection's rows."""
		other = self.paid_guest_gift()
		gift = make_gift(self.fund, 40, church=self.branch_a, donor_name="Guest", email="guest@example.com")

		frappe.set_user(self.finance)
		gift = frappe.get_doc("Online Donation", gift.name).update(
			{"collection": other.collection, "person": self.person}
		)
		with self.assertRaises(frappe.ValidationError):
			gift.save()
		frappe.set_user("Administrator")

		self.assertFalse(frappe.db.get_value("Online Donation", gift.name, "collection"))
		self.assertFalse(frappe.db.get_value("Donation", {"parent": other.collection}, "person"))

	def test_a_refunded_gift_cannot_be_linked(self):
		gift = self.paid_guest_gift()
		frappe.get_doc("Collection", gift.collection).cancel()
		comments = self.comments_on(gift.collection)

		with self.assertRaises(frappe.ValidationError):
			self.link(gift, self.finance)
		frappe.set_user("Administrator")

		self.assertFalse(frappe.db.get_value("Online Donation", gift.name, "person"))
		self.assertFalse(frappe.db.get_value("Donation", {"parent": gift.collection}, "person"))
		self.assertEqual(self.comments_on(gift.collection), comments)

	def test_church_staff_cannot_link_a_gift(self):
		gift = self.paid_guest_gift()

		with self.assertRaises(frappe.PermissionError):
			self.link(gift, self.staff)
		frappe.set_user("Administrator")

		self.assertFalse(frappe.db.get_value("Online Donation", gift.name, "person"))
		self.assertFalse(frappe.db.get_value("Donation", {"parent": gift.collection}, "person"))
