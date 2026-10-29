# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.utils import add_days, today
from frappe.website.doctype.web_form.web_form import accept
from frappe.www.list import get_list_data

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


class TestPledgeWebForm(RollbackEachTest):
	"""The `pledge` web form: a member pledges for themselves, to an open campaign of their church."""

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
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)

	def new_form(self):
		"""The rendered new pledge form: (campaign options, page script)."""
		frappe.local.form_dict = frappe._dict(is_new=1)
		frappe.local.path = "pledge/new"
		context = frappe._dict()
		frappe.get_doc("Web Form", "pledge").get_context(context)
		field = next(f for f in context.web_form_doc.web_form_fields if f.fieldname == "campaign")
		return {option["value"] for option in json.loads(field.options)}, context.script

	def pledge_through_the_form(self, campaign, **values):
		data = {"doctype": "Pledge", "campaign": campaign, "amount": 250, "frequency": "Monthly", **values}
		return accept("pledge", frappe.as_json(data))

	def test_the_form_lists_only_the_open_campaigns_of_the_members_church(self):
		frappe.set_user(self.member)
		options, script = self.new_form()
		self.assertEqual(options, {self.open_a})
		self.assertIn('if ("1" === "1") return;', script)

	def test_a_login_with_no_person_is_offered_no_campaign(self):
		frappe.set_user(ensure_user("_test_pledge_no_person@example.com", "NoPerson"))
		options, script = self.new_form()
		self.assertEqual(options, set())
		self.assertIn('if ("0" === "1") return;', script)

	def test_a_single_church_site_lists_every_open_campaign(self):
		force_single_church()
		frappe.set_user(self.member)
		options, _script = self.new_form()
		# The site may hold other open campaigns, such as the sample data's.
		self.assertLessEqual({self.open_a, self.open_b}, options)
		self.assertNotIn(self.ended_a, options)

	def test_a_member_pledges_for_themselves(self):
		frappe.set_user(self.member)
		pledge = self.pledge_through_the_form(self.open_a, person=self.stranger)

		self.assertEqual(pledge.person, self.person)
		self.assertEqual(pledge.church, self.branch_a)
		self.assertEqual(pledge.amount, 250)

	def test_a_desk_user_pledges_for_themselves_on_the_form(self):
		staff = ensure_user("_test_pledge_staff@example.com", "PledgeStaff", roles=("Church Finance",))
		set_user_church(staff, self.branch_a)
		own = make_person("_Test Pledge", "Staff", church=self.branch_a, user=staff).name
		frappe.set_user(staff)

		pledge = self.pledge_through_the_form(self.open_a, person=self.stranger)
		self.assertEqual(pledge.person, own)
		with self.assertRaises(frappe.PermissionError):
			self.pledge_through_the_form(self.open_b)

	def test_staff_cannot_take_over_another_persons_pledge_on_the_form(self):
		staff = ensure_user(
			"_test_pledge_treasurer@example.com", "PledgeTreasurer", roles=("Church Staff", "Church Finance")
		)
		set_user_church(staff, self.branch_a)
		own = make_person("_Test Pledge", "Treasurer", church=self.branch_a, user=staff).name
		frappe.set_user(staff)
		desk_pledge = frappe.get_doc(
			{"doctype": "Pledge", "campaign": self.open_a, "person": self.stranger, "amount": 500}
		).insert()
		own_pledge = self.pledge_through_the_form(self.open_a)

		listed = {row.name for row in get_list_data("Pledge", web_form_name="pledge")}
		self.assertEqual(listed, {own_pledge.name})

		with self.assertRaises(frappe.PermissionError):
			self.pledge_through_the_form(self.open_a, name=desk_pledge.name, amount=600)
		self.assertEqual(frappe.db.get_value("Pledge", desk_pledge.name, "person"), self.stranger)

		edited = self.pledge_through_the_form(self.open_a, name=own_pledge.name, amount=600)
		self.assertEqual((edited.person, edited.amount), (own, 600))

	def test_a_member_cannot_pledge_to_another_church_or_an_ended_campaign(self):
		frappe.set_user(self.member)
		for campaign in (self.open_b, self.ended_a):
			with self.subTest(campaign), self.assertRaises(frappe.PermissionError):
				self.pledge_through_the_form(campaign)

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

	def test_the_form_has_no_person_field(self):
		fields = {field.fieldname for field in frappe.get_doc("Web Form", "pledge").web_form_fields}
		self.assertEqual(fields, {"campaign", "amount", "frequency"})
