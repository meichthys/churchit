# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch
from urllib.parse import quote

import frappe
from frappe.utils import add_days, today

from churchit.church_finances.doctype.pledge.test_pledge import make_campaign, make_fund, make_pledge
from churchit.church_website.pages import sync_page_switches
from churchit.portal import giving
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

MEMBER = "portal-giving-member@example.com"
OTHER = "portal-giving-other@example.com"
PERIOD = ("2029-01-01", "2029-12-31")


def switch_page(route, enabled):
	features = frappe.get_single("Church Features")
	features.get("website_pages", {"route": route})[0].enabled = enabled
	features.save()


class TestMemberAppGiving(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		sync_page_switches()
		cls.fund_a = make_fund("_Test Portal Fund A", cls.branch_a).name
		fund_b = make_fund("_Test Portal Fund B", cls.branch_b).name
		cls.campaign_a = make_campaign("_Test Portal Campaign A", cls.fund_a, cls.branch_a).name
		cls.campaign_b = make_campaign("_Test Portal Campaign B", fund_b, cls.branch_b).name
		cls.ended_a = make_campaign(
			"_Test Portal Ended A", cls.fund_a, cls.branch_a, end_date=add_days(today(), -1)
		).name
		cls.member = ensure_user(MEMBER, "PortalGiver")
		cls.other = ensure_user(OTHER, "PortalOther")
		cls.person = make_person("_Test Portal", "Giver", user=cls.member, church=cls.branch_a).name
		cls.other_person = make_person("_Test Portal", "Other", user=cls.other, church=cls.branch_a).name
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		frappe.set_user(self.member)

	def as_staff(self, make, *args, **values):
		"""Run *make* as Administrator: a member's save would take the pledge for themselves."""
		frappe.set_user("Administrator")
		try:
			return make(*args, **values)
		finally:
			frappe.set_user(self.member)

	def make_statement(self, person, **values):
		return frappe.get_doc(
			{
				"doctype": "Giving Statement",
				"person": person,
				"from_date": PERIOD[0],
				"to_date": PERIOD[1],
				**values,
			}
		).insert(ignore_permissions=True)

	def test_a_member_sees_their_own_pledges_with_the_receipt_amounts(self):
		mine = self.as_staff(make_pledge, self.campaign_a, self.person, amount=500).name
		self.as_staff(make_pledge, self.campaign_a, self.other_person, amount=70)

		result = giving.get_pledges()

		self.assertEqual([row["name"] for row in result["items"]], [mine])
		row = result["items"][0]
		self.assertEqual(row["campaign_title"], "_Test Portal Campaign A")
		self.assertIn("500.00", row["pledged_display"])
		self.assertEqual(row["percent"], 0)
		self.assertIn(mine, result["existing"].values())

	def test_a_pledge_counts_the_members_gifts_toward_it(self):
		self.as_staff(make_pledge, self.campaign_a, self.person, amount=500)
		frappe.set_user("Administrator")
		payment_type = ensure("Payment Type", {"type": "Cash"})
		frappe.get_doc(
			{
				"doctype": "Collection",
				"date": today(),
				"church": self.branch_a,
				"expected_total": 120,
				"donations": [
					{"payment_type": payment_type, "fund": self.fund_a, "person": self.person, "amount": 120}
				],
			}
		).insert(ignore_permissions=True).submit()
		frappe.set_user(self.member)

		row = giving.get_pledges()["items"][0]

		self.assertIn("120.00", row["given_display"])
		self.assertIn("380.00", row["remaining_display"])
		self.assertEqual(row["percent"], 24)

	def make_give_pledge(self, **campaign_values):
		"""A pledge by the member to a new campaign on a fund that takes gifts."""
		frappe.set_user("Administrator")
		fund = make_fund("_Test Portal Give Fund", self.branch_a, allow_giving=1).name
		campaign = make_campaign("_Test Portal Give Campaign", fund, self.branch_a, **campaign_values).name
		pledge = make_pledge(campaign, self.person, amount=500).name
		frappe.set_user(self.member)
		return fund, pledge

	def test_a_pledge_to_a_running_campaign_links_to_the_give_page(self):
		fund, _pledge = self.make_give_pledge()

		row = giving.get_pledges()["items"][0]

		self.assertEqual(row["give_path"], f"/give?church={quote(self.branch_a)}&fund={quote(fund)}")

	def test_a_pledge_has_no_give_link_when_the_fund_takes_no_gifts(self):
		fund, _pledge = self.make_give_pledge()
		frappe.db.set_value("Fund", fund, "allow_giving", 0)

		self.assertIsNone(giving.get_pledges()["items"][0]["give_path"])

	def test_a_pledge_has_no_give_link_when_the_campaign_has_ended(self):
		self.make_give_pledge(end_date=add_days(today(), -1))

		self.assertIsNone(giving.get_pledges()["items"][0]["give_path"])

	def test_a_pledge_has_no_give_link_before_the_campaign_starts(self):
		self.make_give_pledge(start_date=add_days(today(), 1))

		self.assertIsNone(giving.get_pledges()["items"][0]["give_path"])

	def test_a_pledge_has_no_give_link_when_it_is_fully_given(self):
		fund, _pledge = self.make_give_pledge()
		frappe.set_user("Administrator")
		payment_type = ensure("Payment Type", {"type": "Cash"})
		frappe.get_doc(
			{
				"doctype": "Collection",
				"date": today(),
				"church": self.branch_a,
				"expected_total": 500,
				"donations": [
					{"payment_type": payment_type, "fund": fund, "person": self.person, "amount": 500}
				],
			}
		).insert(ignore_permissions=True).submit()
		frappe.set_user(self.member)

		row = giving.get_pledges()["items"][0]

		self.assertEqual(row["percent"], 100)
		self.assertIsNone(row["give_path"])

	def test_the_amounts_use_the_site_currency_not_the_online_gifts_currency(self):
		"""Giving Settings names the currency that online gifts are charged in, which can differ."""
		self.as_staff(make_pledge, self.campaign_a, self.person, amount=500)
		frappe.db.set_single_value("Giving Settings", "currency", "USD")
		get_default = frappe.db.get_default

		with patch.object(
			frappe.db,
			"get_default",
			lambda key, *args, **kwargs: "EUR" if key == "currency" else get_default(key, *args, **kwargs),
		):
			row = giving.get_pledges()["items"][0]

		for display in (row["pledged_display"], row["given_display"], row["remaining_display"]):
			self.assertIn("€", display)
			self.assertNotIn("$", display)

	def test_only_the_open_campaigns_of_the_members_church_are_offered(self):
		names = {row["name"] for row in giving.get_pledges()["campaigns"]}

		self.assertIn(self.campaign_a, names)
		self.assertNotIn(self.campaign_b, names)
		self.assertNotIn(self.ended_a, names)

	def test_a_pledge_staff_made_cannot_be_edited_and_is_marked_so(self):
		self.as_staff(make_pledge, self.campaign_a, self.person)
		frappe.db.set_value("Pledge", {"person": self.person}, "owner", "Administrator")

		self.assertFalse(giving.get_pledges()["items"][0]["can_edit"])

	def test_a_pledge_to_an_ended_campaign_cannot_be_edited(self):
		self.as_staff(make_pledge, self.ended_a, self.person)
		frappe.db.set_value("Pledge", {"person": self.person}, "owner", self.member)

		self.assertFalse(giving.get_pledges()["items"][0]["can_edit"])

	def test_a_member_makes_a_pledge_for_themselves(self):
		name = giving.save_pledge(self.campaign_a, 120, "Monthly")

		pledge = frappe.get_doc("Pledge", name)
		self.assertEqual((pledge.person, pledge.amount, pledge.frequency), (self.person, 120, "Monthly"))

	def test_a_member_cannot_pledge_to_another_churchs_or_an_ended_campaign(self):
		for campaign in (self.campaign_b, self.ended_a):
			with self.assertRaises(frappe.PermissionError):
				giving.save_pledge(campaign, 10, "One Time")

	def test_a_member_changes_their_own_pledge_but_not_another_members(self):
		own = giving.save_pledge(self.campaign_a, 50, "One Time")
		theirs = self.as_staff(make_pledge, self.campaign_a, self.other_person).name

		self.assertEqual(giving.save_pledge(self.campaign_a, 75, "Weekly", own), own)
		self.assertEqual(frappe.db.get_value("Pledge", own, "amount"), 75)
		with self.assertRaises(frappe.PermissionError):
			giving.save_pledge(self.campaign_a, 75, "Weekly", theirs)

	def test_a_pledge_needs_an_amount_above_zero(self):
		with self.assertRaises(frappe.ValidationError):
			giving.save_pledge(self.campaign_a, 0, "One Time")

	def test_a_desk_user_with_a_person_pledges_only_for_themselves(self):
		"""Staff take the staff path on a plain save, so the app sets its own flag."""
		staff = ensure_user(
			"portal-giving-staff@example.com", "PortalStaff", roles=("Church Staff", "Church Finance")
		)
		person = self.as_staff(make_person, "_Test Portal", "Staff", user=staff, church=self.branch_a).name
		frappe.set_user(staff)

		name = giving.save_pledge(self.campaign_a, 40, "One Time")

		self.assertEqual(frappe.db.get_value("Pledge", name, "person"), person)

	def test_staff_cannot_take_over_another_persons_pledge(self):
		staff = ensure_user(
			"portal-giving-treasurer@example.com", "PortalTreasurer", roles=("Church Staff", "Church Finance")
		)
		self.as_staff(make_person, "_Test Portal", "Treasurer", user=staff, church=self.branch_a)
		desk_pledge = self.as_staff(make_pledge, self.campaign_a, self.other_person, amount=500).name
		frappe.set_user(staff)

		with self.assertRaises(frappe.PermissionError):
			giving.save_pledge(self.campaign_a, 600, "One Time", desk_pledge)

		self.assertEqual(frappe.db.get_value("Pledge", desk_pledge, "person"), self.other_person)
		self.assertEqual(frappe.db.get_value("Pledge", desk_pledge, "amount"), 500)

	def test_a_login_with_no_person_is_refused(self):
		frappe.set_user(ensure_user("portal-giving-nobody@example.com", "Nobody"))
		for call in (giving.get_pledges, giving.get_statements):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_a_switched_off_page_is_refused(self):
		self.as_staff(switch_page, "pledge", 0)
		self.as_staff(switch_page, "statements", 0)
		for call in (giving.get_pledges, giving.get_statements):
			with self.assertRaises(frappe.PermissionError):
				call()
		with self.assertRaises(frappe.PermissionError):
			giving.save_pledge(self.campaign_a, 10, "One Time")

	def test_staff_saving_a_members_pledge_tells_that_members_open_app(self):
		with patch("churchit.portal.realtime.frappe.publish_realtime") as publish:
			pledge = self.as_staff(make_pledge, self.campaign_a, self.person)

		publish.assert_any_call(
			"churchit_portal", {"topic": "pledges", "name": pledge.name}, user=self.member, after_commit=True
		)

	def test_statements_list_the_members_own_and_not_another_persons(self):
		mine = self.make_statement(self.person).name
		self.make_statement(self.other_person)

		items = giving.get_statements()["items"]

		self.assertEqual([row["name"] for row in items], [mine])
		self.assertEqual(items[0]["to_date"], PERIOD[1])

	def test_a_household_statement_is_listed_for_every_member(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Portal Household"}).insert(
			ignore_permissions=True
		)
		spouse = self.as_staff(
			make_person, "_Test Portal", "Spouse", family=family.name, church=self.branch_a
		).name
		frappe.db.set_value("Person", self.person, "family", family.name)
		household = self.make_statement(spouse, family=family.name).name

		self.assertIn(household, [row["name"] for row in giving.get_statements()["items"]])
