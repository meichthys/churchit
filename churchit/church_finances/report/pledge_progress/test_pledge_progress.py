# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_finances.doctype.pledge.test_pledge import make_campaign, make_fund, make_pledge
from churchit.church_finances.report.pledge_progress.pledge_progress import execute
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches


def give(fund, gifts, date, church, submit=True):
	"""A Collection on *date* with one Cash gift to *fund* for each (person, amount) of *gifts*."""
	payment_type = ensure("Payment Type", {"type": "Cash"})
	collection = frappe.get_doc(
		{
			"doctype": "Collection",
			"date": date,
			"church": church,
			"expected_total": sum(amount for _person, amount in gifts),
			"donations": [
				{"payment_type": payment_type, "fund": fund, "person": person, "amount": amount}
				for person, amount in gifts
			],
		}
	).insert(ignore_permissions=True)
	if submit:
		collection.submit()
	return collection


class TestPledgeProgress(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.fund = make_fund("_Test Progress Fund", cls.branch_a).name
		cls.other_fund = make_fund("_Test Progress Other Fund", cls.branch_a).name
		cls.campaign = make_campaign(
			"_Test Progress Campaign", cls.fund, cls.branch_a, "2031-03-01", "2031-03-31", goal_amount=1000
		).name
		cls.giver = make_person("_Test Progress", "Giver", church=cls.branch_a).name
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Progress Household"}).insert(
			ignore_permissions=True
		)
		cls.family = family.name
		cls.parent = make_person("_Test Progress", "Parent", church=cls.branch_a, family=cls.family).name
		cls.child = make_person("_Test Progress", "Child", church=cls.branch_a, family=cls.family).name
		make_pledge(cls.campaign, cls.giver, amount=300, frequency="Monthly")
		make_pledge(cls.campaign, cls.parent, amount=200, family=cls.family)
		cls.addClassCleanup(frappe.clear_cache)

	def rows(self, filters=None):
		data = execute({"campaign": self.campaign, **(filters or {})})[1]
		campaign = next(row for row in data if not row.get("person"))
		by_person = {row["person"]: row for row in data if row.get("person")}
		return campaign, by_person

	def test_a_gift_counts_until_the_end_of_the_last_day(self):
		give(self.fund, [(self.giver, 100)], "2031-03-31 23:30:00", self.branch_a)
		give(self.fund, [(self.giver, 50)], "2031-04-01 00:00:00", self.branch_a)
		give(self.fund, [(self.giver, 25)], "2031-02-28 23:59:00", self.branch_a)

		campaign, pledges = self.rows()

		self.assertEqual(pledges[self.giver]["received"], 100)
		self.assertEqual(pledges[self.giver]["progress"], 33.3)
		self.assertEqual(campaign["received"], 100)
		self.assertEqual(campaign["pledged"], 500)
		self.assertEqual(campaign["goal_amount"], 1000)
		self.assertEqual(campaign["progress"], 10)

	def test_a_household_pledge_counts_every_members_gifts(self):
		give(
			self.fund, [(self.child, 40), (self.parent, 60), (None, 5)], "2031-03-10 10:00:00", self.branch_a
		)

		campaign, pledges = self.rows()

		self.assertEqual(pledges[self.parent]["received"], 100)
		self.assertEqual(pledges[self.giver]["received"], 0)
		self.assertEqual(campaign["received"], 105)

	def test_only_submitted_gifts_to_the_campaign_fund_count(self):
		give(self.fund, [(self.giver, 70)], "2031-03-10 10:00:00", self.branch_a, submit=False)
		give(self.other_fund, [(self.giver, 80)], "2031-03-10 10:00:00", self.branch_a)
		give(self.fund, [(self.giver, 90)], "2031-03-11 10:00:00", self.branch_a).cancel()

		_campaign, pledges = self.rows()

		self.assertEqual(pledges[self.giver]["received"], 0)

	def test_an_expense_from_the_fund_does_not_change_progress(self):
		give(self.fund, [(self.giver, 100)], "2031-03-10 10:00:00", self.branch_a)
		before = self.rows()
		expense_type = ensure(
			"Expense Type",
			{"type": "_Test Progress Expense"},
			{"type": "_Test Progress Expense", "fund": self.fund},
		)
		frappe.get_doc(
			{
				"doctype": "Expense",
				"title": "_Test Progress Expense",
				"type": expense_type,
				"amount": 60,
				"date": "2031-03-15 10:00:00",
				"church": self.branch_a,
			}
		).insert(ignore_permissions=True).submit()

		self.assertEqual(self.rows(), before)

	def test_another_church_sees_none_of_the_campaign(self):
		reader = ensure_user("_test_progress_finance_b@example.com", "Progress", roles=("Church Finance",))
		set_user_church(reader, self.branch_b)
		frappe.set_user(reader)

		self.assertNotIn(self.campaign, {row["campaign"] for row in execute({})[1]})
		with self.assertRaises(frappe.PermissionError):
			execute({"campaign": self.campaign})
