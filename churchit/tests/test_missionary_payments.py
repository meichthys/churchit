# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Integration tests for missionary support payments and fund allocation.

Covers:
- Missionary fund auto-creation on first donation
- Donation auto-allocation to missionary's fund
- Fund balance updates through the existing collection/donation flow
- Online giving with missionary selection
- Missionary Support Schedule doctype
- Missionary Support report execution
- Missions workspace quick list
- Portal member view of missionary donations
"""

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.collection.collection import add_single_donation
from churchit.church_finances.doctype.donation.donation import Donation
from churchit.church_finances.doctype.fund.fund import get_or_create_missionary_fund, get_missionary_fund
from churchit.church_finances.doctype.online_donation.online_donation import (
	OnlineDonation,
)
from churchit.church_missions.doctype.missionary.missionary import Missionary
from churchit.church_missions.doctype.missionary_support_schedule.missionary_support_schedule import (
	MissionarySupportSchedule,
)
from churchit.church_scope import church_filters
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)


class TestMissionaryFundAutoCreation(FrappeTestCase):
	"""Tests that a missionary's fund is created automatically on first donation."""

	def setUp(self):
		force_single_church()
		super().setUp()
		self.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "publish": 1},
		)
		self.person = make_person("_Test Missionary Donor", "Donor")
		frappe.set_user(self.person.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_get_or_create_creates_fund_on_first_call(self):
		"""The first call creates a fund named 'Missionary: {title}'."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		self.assertEqual(fund_name, f"Missionary: {self.missionary}")

		# Second call returns the same name without creating again
		fund_name2 = get_or_create_missionary_fund(self.missionary)
		self.assertEqual(fund_name, fund_name2)

	def test_get_or_create_sets_shared_and_giving_flags(self):
		"""The created fund is shared and allows giving."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		fund = frappe.db.get_value("Fund", fund_name, ["is_shared", "allow_giving", "is_tax_deductible", "balance", "goal_amount"], as_dict=True)
		self.assertTrue(fund.is_shared)
		self.assertTrue(fund.allow_giving)
		self.assertTrue(fund.is_tax_deductible)
		self.assertEqual(fund.balance, 0)
		self.assertEqual(fund.goal_amount, 0)

	def test_get_or_create_uses_missionary_church(self):
		"""The fund carries the missionary's church."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		fund = frappe.db.get_value("Fund", fund_name, "church", as_dict=True)
		self.assertEqual(fund.church, self.missionary.church)

	def test_add_single_donation_allocates_to_missionary_fund(self):
		"""A donation through add_single_donation goes to the missionary's fund."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		collection_name = add_single_donation(
			self.missionary.church,
			fund_name,
			100.00,
			"Test donation",
			person=self.person.name,
		)

		# Verify the Collection has the right fund
		collection = frappe.get_doc("Collection", collection_name)
		for donation in collection.donations:
			self.assertEqual(donation.fund, fund_name)
			self.assertEqual(donation.amount, 100.00)

	def test_fund_balance_increases_after_donation(self):
		"""The missionary's fund balance increases by the donation amount."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		initial_balance = frappe.db.get_value("Fund", fund_name, "balance")

		add_single_donation(
			self.missionary.church,
			fund_name,
			50.00,
			"Test donation",
			person=self.person.name,
		)

		new_balance = frappe.db.get_value("Fund", fund_name, "balance")
		self.assertEqual(new_balance, initial_balance + 50.00)


class TestDonationMissionaryField(FrappeTestCase):
	"""Tests that the missionary field flows through the donation chain."""

	def setUp(self):
		force_single_church()
		super().setUp()
		self.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "publish": 1},
		)
		self.person = make_person("_Test Missionary Donor", "Donor")
		frappe.set_user(self.person.user)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_donation_stores_missionary_link(self):
		"""A Donation row records the missionary link."""
		donation = Donation(
			{
				"doctype": "Donation",
				"parent": "_Test Collection",
				"parenttype": "Collection",
				"amount": 100.00,
				"fund": "General",
				"payment_type": "Cash",
				"person": self.person.name,
				"missionary": self.missionary,
			}
		)
		donation.insert(ignore_permissions=True)

		self.assertEqual(donation.missionary, self.missionary)

	def test_donation_without_missionary_is_null(self):
		"""A donation without a missionary field is None."""
		donation = Donation(
			{
				"doctype": "Donation",
				"parent": "_Test Collection",
				"parenttype": "Collection",
				"amount": 100.00,
				"fund": "General",
				"payment_type": "Cash",
				"person": self.person.name,
			}
		)
		donation.insert(ignore_permissions=True)

		self.assertIsNone(donation.missionary)

	def test_multiple_donations_to_same_missionary_accumulate(self):
		"""Multiple donations to the same missionary all link to it."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		for i in range(3):
			add_single_donation(
				self.missionary.church,
				fund_name,
				25.00,
				"Test donation",
				person=self.person.name,
			)

		# All donations should reference the missionary
		collections = frappe.get_all(
			"Collection",
			filters=["fund", fund_name],
			fields=["name", "donations"],
		)
		for col in collections:
			for d in col.get("donations", []):
				self.assertEqual(d.fund, fund_name)


class TestOnlineDonationMissionaryAllocation(FrappeTestCase):
	"""Tests that online donations allocate to the missionary's fund."""

	def setUp(self):
		force_single_church()
		super().setUp()
		self.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "publish": 1},
		)
		self.person = make_person("_Test Online Donor", "Donor")
		frappe.set_user(self.person.user)
		# Set up a gateway for online giving
		from churchit.church_finances.doctype.giving_settings.test_giving_settings import (
			make_gateway,
			without_payments,
		)
		self.gateway = make_gateway("_Test Gateway")
		settings = frappe.get_doc("Giving Settings")
		settings.enabled = True
		settings.gateways = [self.gateway]
		settings.save(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_record_donation_uses_missionary_fund(self):
		"""record_donation allocates to the missionary's fund when missionary is set."""
		# Create the missionary fund first
		fund_name = get_or_create_missionary_fund(self.missionary)

		# Create an Online Donation with missionary set
		donation = OnlineDonation(
			{
				"doctype": "Online Donation",
				"church": self.missionary.church,
				"amount": 100.00,
				"fund": "General",
				"person": self.person.name,
				"donor_name": "_Test Online Donor",
				"email": "_test_online@example.com",
				"notes": "Online gift",
				"currency": "USD",
				"payment_gateway": self.gateway.payment_gateway,
				"status": "Pending",
				"missionary": self.missionary,
			}
		)
		donation.insert(ignore_permissions=True)

		# Record the donation - this should allocate to the missionary's fund
		donation.record_donation()

		# The collection should have the missionary's fund
		collection = frappe.get_doc("Collection", donation.collection)
		for d in collection.donations:
			self.assertEqual(d.fund, fund_name)
			self.assertEqual(d.amount, 100.00)

	def test_fund_balance_updates_after_online_donation(self):
		"""The missionary's fund balance increases after an online donation."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		initial_balance = frappe.db.get_value("Fund", fund_name, "balance")

		donation = OnlineDonation(
			{
				"doctype": "Online Donation",
				"church": self.missionary.church,
				"amount": 75.00,
				"fund": "General",
				"person": self.person.name,
				"donor_name": "_Test Online Donor",
				"email": "_test_online@example.com",
				"notes": "Online gift",
				"currency": "USD",
				"payment_gateway": self.gateway.payment_gateway,
				"status": "Pending",
				"missionary": self.missionary,
			}
		)
		donation.insert(ignore_permissions=True)
		donation.record_donation()

		new_balance = frappe.db.get_value("Fund", fund_name, "balance")
		self.assertEqual(new_balance, initial_balance + 75.00)

	def test_online_donation_without_missionary_uses_general_fund(self):
		"""An online donation without a missionary uses the general fund."""
		# Create a general fund
		general_fund = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test General Fund", "allow_giving": 1}
		).insert(ignore_permissions=True)

		donation = OnlineDonation(
			{
				"doctype": "Online Donation",
				"church": self.missionary.church,
				"amount": 50.00,
				"fund": general_fund.name,
				"person": self.person.name,
				"donor_name": "_Test Online Donor",
				"email": "_test_online@example.com",
				"notes": "Online gift",
				"currency": "USD",
				"payment_gateway": self.gateway.payment_gateway,
				"status": "Pending",
				"missionary": None,
			}
		)
		donation.insert(ignore_permissions=True)
		donation.record_donation()

		collection = frappe.get_doc("Collection", donation.collection)
		for d in collection.donations:
			self.assertEqual(d.fund, general_fund.name)


class TestMissionarySupportSchedule(FrappeTestCase):
	"""Tests for the Missionary Support Schedule doctype."""

	def setUp(self):
		force_single_church()
		super().setUp()
		self.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "publish": 1},
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_create_schedule_with_valid_data(self):
		"""A schedule can be created with valid data."""
		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 50.00,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		self.assertEqual(schedule.missionary, self.missionary)
		self.assertEqual(schedule.monthly_amount, 50.00)
		self.assertEqual(schedule.status, "Active")
		self.assertEqual(schedule.total_committed, 50.00)

	def test_total_committed_calculates_correctly(self):
		"""total_committed equals monthly_amount times months in period."""
		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 100.00,
				"start_date": "2026-01-01",
				"end_date": "2026-06-30",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		# Jan-Jun = 6 months
		self.assertEqual(schedule.total_committed, 600.00)

	def test_total_committed_zero_when_no_amount(self):
		"""total_committed is 0 when monthly_amount is 0."""
		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 0,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		self.assertEqual(schedule.total_committed, 0)

	def test_validate_rejects_invalid_dates(self):
		"""Validation rejects end_date before start_date."""
		with self.assertRaises(ValidationError):
			schedule = MissionarySupportSchedule(
				{
					"doctype": "Missionary Support Schedule",
					"missionary": self.missionary,
					"monthly_amount": 50.00,
					"start_date": "2026-12-01",
					"end_date": "2026-01-01",
					"status": "Active",
				}
			)
			schedule.insert(ignore_permissions=True)

	def test_validate_rejects_invalid_status(self):
		"""Validation rejects an invalid status value."""
		with self.assertRaises(ValidationError):
			schedule = MissionarySupportSchedule(
				{
					"doctype": "Missionary Support Schedule",
					"missionary": self.missionary,
					"monthly_amount": 50.00,
					"start_date": "2026-01-01",
					"end_date": "2026-12-31",
					"status": "Invalid Status",
				}
			)
			schedule.insert(ignore_permissions=True)

	def test_get_received_to_date(self):
		"""get_received_to_date sums donations to this schedule's fund."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		add_single_donation(
			self.missionary.church,
			fund_name,
			30.00,
			"Test donation",
			person=None,
		)

		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 50.00,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		received = schedule.get_received_to_date()
		self.assertEqual(received, 30.00)

	def test_get_balance(self):
		"""get_balance = total_committed - received_to_date."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		add_single_donation(
			self.missionary.church,
			fund_name,
			20.00,
			"Test donation",
			person=None,
		)

		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 100.00,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		# total_committed = 100 * 12 = 1200
		# received = 20
		# balance = 1200 - 20 = 1180
		self.assertEqual(schedule.get_balance(), 1180.00)

	def test_get_next_due_date(self):
		"""get_next_due_date calculates the next payment date."""
		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 50.00,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		# Next due date should be the first day of the next month
		next_due = schedule.get_next_due_date()
		self.assertEqual(next_due, "2026-02-01")

	def test_get_last_payment_date(self):
		"""get_last_payment_date finds the most recent donation date."""
		fund_name = get_or_create_missionary_fund(self.missionary)
		add_single_donation(
			self.missionary.church,
			fund_name,
			40.00,
			"Test donation",
			person=None,
		)

		schedule = MissionarySupportSchedule(
			{
				"doctype": "Missionary Support Schedule",
				"missionary": self.missionary,
				"monthly_amount": 50.00,
				"start_date": "2026-01-01",
				"end_date": "2026-12-31",
				"status": "Active",
			}
		)
		schedule.insert(ignore_permissions=True)

		last_payment = schedule.get_last_payment_date()
		self.assertIsNotNone(last_payment)


class TestMissionsWorkspaceQuickList(FrappeTestCase):
	"""Tests that the Missions workspace has the quick list."""

	def test_quick_list_exists(self):
		"""The Missions workspace has a 'Missionaries behind on support' quick list."""
		workspace = frappe.get_cached_doc("Workspace", "Missions")
		quick_lists = [ql.report for ql in workspace.quick_lists]
		self.assertIn("Missionary Support", quick_lists)

	def test_quick_list_filter(self):
		"""The quick list filters on balance > 0."""
		workspace = frappe.get_cached_doc("Workspace", "Missions")
		for ql in workspace.quick_lists:
			if ql.report == "Missionary Support":
				filters = ql.filters
				self.assertIn("fieldname", filters)
				self.assertEqual(filters["fieldname"], "balance")
				self.assertEqual(filters["condition"], ">")
				self.assertEqual(filters["value"], 0)
				break
		else:
			self.fail("Quick list not found")


class TestPortalMemberView(RollbackEachTest):
	"""Tests that portal members can see their missionary donations."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_manager_a@example.com", "Manager A", roles=("Church Manager",))
		cls.manager_b = ensure_user("_manager_b@example.com", "Manager B", roles=("Church Manager",))
		cls.member_a = ensure_user("_member_a@example.com", "Member A", roles=("Church User",))
		cls.member_b = ensure_user("_member_b@example.com", "Member B", roles=("Church User",))
		cls.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "church": cls.branch_a, "publish": 1},
		)
		cls.person_a = make_person("_Test Member A", "Member", user=cls.member_a)
		cls.person_b = make_person("_Test Member B", "Member", user=cls.member_b)
		cls.fund_a = ensure("Fund", {"fund": "_Test Missionary Fund A", "is_shared": 1, "allow_giving": 1}, {"church": cls.branch_a})
		cls.fund_b = ensure("Fund", {"fund": "_Test Missionary Fund B", "is_shared": 1, "allow_giving": 1}, {"church": cls.branch_b})

	def setUp(self):
		force_single_church()
		super().setUp()
		self.missionary = ensure(
			"Missionary",
			{"title": "_Test Missionary", "church": self.branch_a, "publish": 1},
		)
		self.person_a = make_person("_Test Member A", "Member", user=self.member_a)
		self.person_b = make_person("_Test Member B", "Member", user=self.member_b)
		self.fund_a = ensure("Fund", {"fund": "_Test Missionary Fund A", "is_shared": 1, "allow_giving": 1}, {"church": self.branch_a})
		self.fund_b = ensure("Fund", {"fund": "_Test Missionary Fund B", "is_shared": 1, "allow_giving": 1}, {"church": self.branch_b})

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_member_sees_own_missionary_donations(self):
		"""A member sees only their own donations earmarked for a missionary."""
		# Member A donates to missionary's fund
		add_single_donation(
			self.branch_a,
			self.fund_a,
			100.00,
			"Test donation",
			person=self.person_a.name,
		)

		# Switch to member A's session
		frappe.set_user(self.member_a)

		# Get collections visible to member A
		collections = frappe.get_all(
			"Collection",
			filters=church_filters(self.branch_a),
			fields=["name", "donations"],
		)

		# Only collections from member A's church should appear
		for col in collections:
			for d in col.get("donations", []):
				self.assertEqual(d.fund, self.fund_a)

	def test_member_cannot_see_other_church_donations(self):
		"""A member cannot see donations from another church."""
		# Member B donates to missionary's fund in branch B
		add_single_donation(
			self.branch_b,
			self.fund_b,
			100.00,
			"Test donation",
			person=self.person_b.name,
		)

		# Switch to member A's session
		frappe.set_user(self.member_a)

		# Get collections visible to member A
		collections = frappe.get_all(
			"Collection",
			filters=church_filters(self.branch_a),
			fields=["name", "donations"],
		)

		# No collections from branch B should appear
		for col in collections:
			for d in col.get("donations", []):
				self.assertNotEqual(d.fund, self.fund_b)

	def test_missionary_fund_auto_created_in_both_churches(self):
		"""Each church gets its own missionary fund when a donation is made."""
		# Make a donation in branch A
		add_single_donation(
			self.branch_a,
			get_or_create_missionary_fund(self.missionary),
			50.00,
			"Test donation",
			person=self.person_a.name,
		)

		# Make a donation in branch B
		add_single_donation(
			self.branch_b,
			get_or_create_missionary_fund(self.missionary),
			50.00,
			"Test donation",
			person=self.person_b.name,
		)

		# Both churches should have their own missionary fund
		fund_a = get_or_create_missionary_fund(self.missionary)
		fund_b = get_or_create_missionary_fund(self.missionary)
		self.assertNotEqual(fund_a, fund_b)
		self.assertEqual(frappe.db.get_value("Fund", fund_a, "church"), self.branch_a)
		self.assertEqual(frappe.db.get_value("Fund", fund_b, "church"), self.branch_b)
