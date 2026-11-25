# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, today

from churchit.church_finances.doctype.pledge.pledge import get_open_campaigns
from churchit.church_foundations.church_access import set_user_church
from churchit.church_scope import SHARED
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
	set_private_people,
)


def make_fund(name, church, **values):
	return frappe.get_doc({"doctype": "Fund", "fund": name, "church": church, **values}).insert(
		ignore_permissions=True
	)


def make_campaign(title, fund, church, start_date=None, end_date=None, **values):
	return frappe.get_doc(
		{
			"doctype": "Pledge Campaign",
			"title": title,
			"fund": fund,
			"church": church,
			"start_date": start_date or add_days(today(), -10),
			"end_date": end_date or add_days(today(), 30),
			**values,
		}
	).insert(ignore_permissions=True)


def make_pledge(campaign, person, amount=100, **values):
	return frappe.get_doc(
		{"doctype": "Pledge", "campaign": campaign, "person": person, "amount": amount, **values}
	).insert(ignore_permissions=True)


class TestPledge(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.fund_a = make_fund("_Test Pledge Fund A", cls.branch_a).name
		cls.fund_b = make_fund("_Test Pledge Fund B", cls.branch_b).name
		cls.campaign_a = make_campaign("_Test Campaign A", cls.fund_a, cls.branch_a).name
		cls.campaign_b = make_campaign("_Test Campaign B", cls.fund_b, cls.branch_b).name
		cls.giver_a = make_person("_Test Pledger", "A", church=cls.branch_a).name
		cls.giver_b = make_person("_Test Pledger", "B", church=cls.branch_b).name
		cls.finance_a = cls.staff("_test_pledge_finance_a@example.com", cls.branch_a)
		cls.finance_b = cls.staff("_test_pledge_finance_b@example.com", cls.branch_b)
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def staff(cls, email, church):
		ensure_user(email, "Pledge Finance", roles=("Church Staff", "Church Finance"))
		set_user_church(email, church)
		return email

	def test_a_pledge_takes_its_campaigns_church(self):
		pledge = make_pledge(self.campaign_a, self.giver_b)
		self.assertEqual(pledge.church, self.branch_a)
		self.assertEqual(pledge.title, "_Test Pledger B - _Test Campaign A")

	def test_a_pledge_for_someone_who_died_saves_with_a_warning(self):
		frappe.db.set_value("Person", self.giver_a, {"is_deceased": 1, "deceased_date": "2020-01-01"})
		frappe.local.message_log = []

		pledge = make_pledge(self.campaign_a, self.giver_a)

		self.assertTrue(frappe.db.exists("Pledge", pledge.name))
		self.assertIn("died on", frappe.local.message_log[-1]["message"])

	def test_a_campaign_takes_the_church_of_whoever_adds_it(self):
		frappe.set_user(self.finance_a)
		campaign = make_campaign("_Test Own Campaign", self.fund_a, SHARED)
		self.assertEqual(campaign.church, self.branch_a)

	def test_pledges_and_campaigns_are_scoped(self):
		mine = make_pledge(self.campaign_a, self.giver_a).name
		theirs = make_pledge(self.campaign_b, self.giver_b).name
		assert_scoped(self, "Pledge", self.finance_a, mine, theirs)
		assert_scoped(self, "Pledge Campaign", self.finance_a, self.campaign_a, self.campaign_b)
		assert_scoped(self, "Pledge Campaign", self.finance_b, self.campaign_b, self.campaign_a)

	def test_a_campaign_cannot_use_another_churchs_fund(self):
		with self.assertRaises(frappe.PermissionError):
			make_campaign("_Test Reaching Campaign", self.fund_b, self.branch_a)

	def test_a_pledge_needs_an_amount_above_zero(self):
		for amount in (0, -5):
			with self.assertRaises(frappe.ValidationError):
				make_pledge(self.campaign_a, self.giver_a, amount=amount)

	def test_a_campaign_cannot_end_before_it_starts(self):
		with self.assertRaises(frappe.ValidationError):
			make_campaign("_Test Backwards", self.fund_a, self.branch_a, today(), add_days(today(), -1))

	def test_staff_cannot_pledge_to_another_churchs_campaign(self):
		frappe.set_user(self.finance_a)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{"doctype": "Pledge", "campaign": self.campaign_b, "person": self.giver_a, "amount": 10}
			).insert()

		pledge = frappe.get_doc(
			{"doctype": "Pledge", "campaign": self.campaign_a, "person": self.giver_a, "amount": 10}
		).insert()
		pledge.campaign = self.campaign_b
		with self.assertRaises(frappe.PermissionError):
			pledge.save()

	def test_staff_cannot_name_another_churchs_person_or_family_in_a_private_directory(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		family_b = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Pledge Family B", "church": self.branch_b}
		).insert(ignore_permissions=True)

		frappe.set_user(self.finance_a)
		for values in ({"person": self.giver_b}, {"person": self.giver_a, "family": family_b.name}):
			with self.subTest(values), self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{"doctype": "Pledge", "campaign": self.campaign_a, "amount": 10, **values}
				).insert()


class TestMemberPledge(RollbackEachTest):
	"""A member pledges for themselves, to an open campaign of their church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.fund_a = make_fund("_Test Pledge Form Fund A", cls.branch_a).name
		cls.fund_b = make_fund("_Test Pledge Form Fund B", cls.branch_b).name
		cls.open_a = make_campaign("_Test Open Campaign A", cls.fund_a, cls.branch_a).name
		cls.ended_a = make_campaign(
			"_Test Ended Campaign A",
			cls.fund_a,
			cls.branch_a,
			add_days(today(), -30),
			add_days(today(), -1),
		).name
		cls.open_b = make_campaign("_Test Open Campaign B", cls.fund_b, cls.branch_b).name
		cls.member = ensure_user("_test_pledge_member@example.com", "PledgeMember")
		cls.person = make_person("_Test Pledge", "Member", church=cls.branch_a, user=cls.member).name
		cls.stranger = make_person("_Test Pledge", "Stranger", church=cls.branch_a).name
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def test_a_member_is_offered_only_the_open_campaigns_of_their_church(self):
		frappe.set_user(self.member)
		offered = set(get_open_campaigns())

		self.assertEqual(offered & {self.open_a, self.open_b, self.ended_a}, {self.open_a})

	def test_a_login_with_no_person_is_offered_no_campaign(self):
		frappe.set_user(ensure_user("_test_pledge_no_person@example.com", "NoPerson"))

		self.assertEqual(get_open_campaigns(), {})

	def test_a_single_church_site_offers_every_open_campaign(self):
		force_single_church()
		frappe.set_user(self.member)
		offered = set(get_open_campaigns())

		self.assertLessEqual({self.open_a, self.open_b}, offered)
		self.assertNotIn(self.ended_a, offered)

	def test_a_member_cannot_pledge_for_another_household(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Other Household"}).insert(
			ignore_permissions=True
		)
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{
					"doctype": "Pledge",
					"campaign": self.open_a,
					"person": self.person,
					"family": family.name,
					"amount": 10,
				}
			).insert()
