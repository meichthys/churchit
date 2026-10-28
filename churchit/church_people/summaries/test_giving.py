# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate, today

from churchit.church_finances.doctype.online_donation.test_online_donation import log_charge
from churchit.church_people.summaries import giving, refresh
from churchit.church_people.summaries.test_serving import queued_people
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

NO_GIFTS = {"first_gift_on": None, "last_gift_on": None, "is_lapsed_giver": 0}


def make_collection(person, date, fund, church=None):
	"""A draft Collection of one 10.00 gift from *person*."""
	return frappe.get_doc(
		{
			"doctype": "Collection",
			"date": date,
			"church": church,
			"expected_total": 10,
			"donations": [{"person": person, "fund": fund, "payment_type": "Cash", "amount": 10}],
		}
	).insert(ignore_permissions=True)


def give(person, date, fund, church=None):
	collection = make_collection(person, date, fund, church)
	collection.submit()
	return collection


class TestGivingSummary(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for payment_type in ("Cash", "Online"):
			ensure("Payment Type", {"type": payment_type})
		cls.fund = ensure("Fund", {"fund": "_Test Giving Summary Fund"})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Giver", "Summary").name

	def summary(self):
		refresh([self.person])
		return frappe.db.get_value("Person", self.person, giving.FIELDS, as_dict=True)

	def online_gift(self, status):
		gift = frappe.get_doc(
			{"doctype": "Online Donation", "amount": 25, "fund": self.fund, "person": self.person}
		).insert(ignore_permissions=True)
		if status == "Completed":
			log_charge(gift)
		gift.on_payment_authorized(status)
		return gift

	def test_first_and_last_gift_up_to_the_end_of_today(self):
		give(self.person, add_days(today(), -400), self.fund)
		give(self.person, add_days(today(), -30), self.fund)
		give(self.person, f"{today()} 23:59:00", self.fund)

		summary = self.summary()

		self.assertEqual(summary.first_gift_on, getdate(add_days(today(), -400)))
		self.assertEqual(summary.last_gift_on, getdate(today()))

	def test_a_paid_online_gift_counts_on_the_day_it_was_paid(self):
		give(self.person, add_days(today(), -60), self.fund)
		self.online_gift("Completed")

		self.assertEqual(self.summary().last_gift_on, getdate(today()))

	def test_a_giver_lapses_after_90_days_without_a_gift_for_up_to_a_year(self):
		for days_ago, is_lapsed in ((90, 0), (91, 1), (365, 1), (366, 0)):
			collection = give(self.person, add_days(today(), -days_ago), self.fund)
			self.assertEqual(self.summary().is_lapsed_giver, is_lapsed, days_ago)
			collection.cancel()

	def test_an_online_gift_not_paid_does_not_count(self):
		self.online_gift("Declined")
		frappe.get_doc(
			{"doctype": "Online Donation", "amount": 5, "fund": self.fund, "person": self.person}
		).insert(ignore_permissions=True)

		self.assertEqual(self.summary(), NO_GIFTS)

	def test_only_submitted_collections_count(self):
		make_collection(self.person, add_days(today(), -5), self.fund)
		give(self.person, add_days(today(), -3), self.fund).cancel()

		self.assertEqual(self.summary(), NO_GIFTS)

	def test_a_collection_dated_in_the_future_does_not_count(self):
		give(self.person, add_days(today(), 7), self.fund)

		self.assertIsNone(self.summary().first_gift_on)

	def test_saving_a_collection_queues_everyone_it_had_or_has(self):
		collection = make_collection(self.person, today(), self.fund)
		other = make_person("_Test Second Giver", "Summary").name
		collection.donations[0].person = other

		self.assertEqual(
			queued_people(lambda: collection.save(ignore_permissions=True)), [sorted([self.person, other])]
		)

	def test_cancelling_a_collection_queues_its_givers_and_clears_the_gift(self):
		collection = give(self.person, add_days(today(), -1), self.fund)
		self.assertEqual(self.summary().last_gift_on, getdate(add_days(today(), -1)))

		self.assertEqual(queued_people(collection.cancel), [[self.person]])
		self.assertIsNone(self.summary().last_gift_on)

	def test_only_finance_reads_the_giving_dates(self):
		give(self.person, add_days(today(), -2), self.fund)
		self.summary()

		for roles, last_gift_on in (
			(("Church Staff",), None),
			(("Church Staff", "Church Finance"), getdate(add_days(today(), -2))),
		):
			email = f"_test_giving_{frappe.scrub(roles[-1])}@example.com"
			frappe.set_user(ensure_user(email, roles[-1], roles=roles))
			person = frappe.get_doc("Person", self.person)
			person.apply_fieldlevel_read_permissions()
			self.assertEqual(person.get("last_gift_on"), last_gift_on, roles)

	def test_a_list_cannot_find_givers_for_someone_who_cannot_read_the_dates(self):
		frappe.set_user(
			ensure_user("_test_giving_church_staff@example.com", "Church Staff", roles=("Church Staff",))
		)

		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Person", filters={"last_gift_on": ("is", "set")})


class TestGivingStaysInItsChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Payment Type", {"type": "Cash"})
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.shared_fund = ensure(
			"Fund", {"fund": "_Test Giving Shared Fund"}, {"fund": "_Test Giving Shared Fund", "is_shared": 1}
		)

	def test_a_gift_at_another_church_does_not_count_even_into_a_shared_fund(self):
		"""A shared fund is a joint pot, but each gift keeps the church that took it."""
		person = make_person("_Test Branch", "Giver", church=self.branch_a).name
		give(person, add_days(today(), -10), self.shared_fund, church=self.branch_b)
		refresh([person])
		self.assertIsNone(frappe.db.get_value("Person", person, "last_gift_on"))

		give(person, add_days(today(), -5), self.shared_fund, church=self.branch_a)
		refresh([person])
		self.assertEqual(
			frappe.db.get_value("Person", person, "first_gift_on"), getdate(add_days(today(), -5))
		)
