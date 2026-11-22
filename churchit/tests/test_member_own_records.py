# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Pledges and sign-ups that staff record for a member: the member reads their own and no one else's."""

import frappe

from churchit.church_finances.doctype.pledge.test_pledge import make_campaign, make_fund, make_pledge
from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries.member_sign_ups import get_sign_up_summary
from churchit.church_people.test_merge import make_family
from churchit.portal.events import get_sign_up, get_sign_ups
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

PLEDGE = "Pledge"
SIGN_UP = "Function Sign-Up"


class TestMemberOwnRecords(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.campaign_a = make_campaign(
			"_Test Own Records Campaign A",
			make_fund("_Test Own Records Fund A", cls.branch_a).name,
			cls.branch_a,
		).name
		cls.campaign_b = make_campaign(
			"_Test Own Records Campaign B",
			make_fund("_Test Own Records Fund B", cls.branch_b).name,
			cls.branch_b,
		).name
		cls.function = make_function("_Test Own Records Picnic", church=cls.branch_a, allow_sign_ups=1).name
		cls.member = ensure_user("_test_own_records_member@example.com", "OwnRecords")
		cls.person = make_person("_Test Own Records", "Member", church=cls.branch_a, user=cls.member).name
		cls.neighbour = ensure_user("_test_own_records_neighbour@example.com", "OwnRecordsNeighbour")
		cls.neighbours_person = make_person(
			"_Test Own Records", "Neighbour", church=cls.branch_a, user=cls.neighbour
		).name
		cls.finance = ensure_user(
			"_test_own_records_finance@example.com",
			"OwnRecordsFinance",
			roles=("Church Staff", "Church Finance"),
		)
		set_user_church(cls.finance, cls.branch_a)
		cls.addClassCleanup(frappe.clear_cache)

	def sign_up(self, person):
		"""A sign-up that staff record for *person*."""
		return frappe.get_doc({"doctype": SIGN_UP, "function": self.function, "person": person}).insert(
			ignore_permissions=True
		)

	def assert_reads_only(self, user, doctype, mine, theirs):
		frappe.set_user(user)
		self.assertIn(mine, frappe.get_list(doctype, pluck="name"))
		self.assertNotIn(theirs, frappe.get_list(doctype, pluck="name"))
		self.assertTrue(frappe.has_permission(doctype, "read", doc=mine))
		self.assertFalse(frappe.has_permission(doctype, "read", doc=theirs))

	def test_a_member_reads_the_pledges_staff_recorded_for_them_and_no_one_elses(self):
		mine = make_pledge(self.campaign_a, self.person).name
		theirs = make_pledge(self.campaign_a, self.neighbours_person).name

		self.assert_reads_only(self.member, PLEDGE, mine, theirs)
		self.assert_reads_only(self.neighbour, PLEDGE, theirs, mine)

	def test_a_household_pledge_is_read_by_each_adult_of_the_household_and_not_a_child(self):
		spouse_user = ensure_user("_test_own_records_spouse@example.com", "OwnRecordsSpouse")
		spouse = make_person("_Test Own Records", "Spouse", church=self.branch_a, user=spouse_user)
		child_user = ensure_user("_test_own_records_child@example.com", "OwnRecordsChild")
		child = make_person("_Test Own Records", "Child", church=self.branch_a, user=child_user)
		family = make_family(
			"_Test Own Records Household", frappe.get_doc("Person", self.person), spouse, child
		)
		for member, role in ((self.person, "Adult"), (spouse.name, "Adult"), (child.name, "Child")):
			frappe.db.set_value(
				"Family Members", {"parent": family.name, "member": member}, "household_role", role
			)
		household = make_pledge(self.campaign_a, self.person, family=family.name).name
		personal = make_pledge(self.campaign_a, self.person).name

		frappe.set_user(spouse_user)
		self.assertIn(household, frappe.get_list(PLEDGE, pluck="name"))
		self.assertTrue(frappe.has_permission(PLEDGE, "read", doc=household))
		self.assertNotIn(personal, frappe.get_list(PLEDGE, pluck="name"))
		self.assertFalse(frappe.has_permission(PLEDGE, "read", doc=personal))
		self.assertFalse(frappe.has_permission(PLEDGE, "write", doc=household))

		frappe.set_user(child_user)
		self.assertNotIn(household, frappe.get_list(PLEDGE, pluck="name"))
		self.assertFalse(frappe.has_permission(PLEDGE, "read", doc=household))

		frappe.set_user(self.neighbour)
		self.assertFalse(frappe.has_permission(PLEDGE, "read", doc=household))

	def test_a_member_cannot_change_a_pledge_staff_recorded(self):
		mine = make_pledge(self.campaign_a, self.person).name
		frappe.set_user(self.member)
		self.assertFalse(frappe.has_permission(PLEDGE, "write", doc=mine))
		pledge = frappe.get_doc(PLEDGE, mine)
		pledge.amount = 1
		with self.assertRaises(frappe.PermissionError):
			pledge.save()

	def test_a_member_reads_no_pledge_of_another_church(self):
		elsewhere = make_pledge(self.campaign_b, self.person).name
		frappe.set_user(self.member)
		self.assertFalse(frappe.has_permission(PLEDGE, "read", doc=elsewhere))
		self.assertNotIn(elsewhere, frappe.get_list(PLEDGE, pluck="name"))

	def test_a_member_reads_the_sign_ups_staff_recorded_for_them_and_no_one_elses(self):
		mine = self.sign_up(self.person).name
		theirs = self.sign_up(self.neighbours_person).name

		self.assert_reads_only(self.member, SIGN_UP, mine, theirs)
		self.assertFalse(frappe.has_permission(SIGN_UP, "write", doc=mine))
		self.assertFalse(frappe.has_permission(SIGN_UP, "delete", doc=mine))

	def test_the_sign_ups_list_holds_only_their_own(self):
		mine = self.sign_up(self.person).name
		self.sign_up(self.neighbours_person)
		frappe.set_user(self.member)
		self.assertEqual([row["name"] for row in get_sign_ups()["items"]], [mine])

	def test_the_sign_ups_list_shows_each_sign_up_with_its_status_and_who_comes(self):
		mine = self.sign_up(self.person).name
		frappe.set_user(self.member)

		(row,) = get_sign_ups()["items"]
		self.assertEqual(
			(row["name"], row["status"], row["attendee_names"]),
			(mine, "Confirmed", ["_Test Own Records Member"]),
		)

	def test_a_sign_up_page_sums_it_up_and_offers_cancel_only_on_the_members_own(self):
		recorded = self.sign_up(self.person).name
		theirs = self.sign_up(self.neighbours_person).name
		lunch = make_function("_Test Own Records Lunch", church=self.branch_a, allow_sign_ups=1).name
		frappe.set_user(self.member)
		own = frappe.get_doc({"doctype": SIGN_UP, "function": lunch}).insert().name

		summary = get_sign_up_summary(recorded)
		self.assertEqual((summary["status"], summary["can_cancel"]), ("Confirmed", False))
		self.assertEqual(summary["attendees"], [{"name": "_Test Own Records Member", "selection": ""}])
		self.assertTrue(get_sign_up_summary(own)["can_cancel"])
		with self.assertRaises(frappe.PermissionError):
			get_sign_up_summary(theirs)

	def test_a_waitlisted_sign_up_page_shows_no_amount_due(self):
		camp = make_function("_Test Own Records Camp", church=self.branch_a, allow_sign_ups=1, capacity=1)
		camp.append("selections", {"selection": "_Test Adult", "price": 20})
		camp.save(ignore_permissions=True)
		for person in (self.neighbours_person, self.person):
			attendees = [{"person": person, "selection": "_Test Adult"}]
			waiting = frappe.get_doc(
				{"doctype": SIGN_UP, "function": camp.name, "person": person, "attendees": attendees}
			).insert(ignore_permissions=True)
		frappe.set_user(self.member)

		summary = get_sign_up_summary(waiting.name)

		self.assertEqual(
			(summary["status"], summary["amount_due"], summary["payment_status"]), ("Waitlisted", "", "")
		)

	def test_the_app_offers_no_edit_on_a_sign_up_staff_recorded(self):
		recorded = self.sign_up(self.person).name
		frappe.set_user(self.member)
		self.assertFalse(get_sign_up(recorded)["can_edit"])

	def test_a_member_still_reads_and_changes_what_they_made(self):
		frappe.set_user(self.member)
		own = frappe.get_doc({"doctype": SIGN_UP, "function": self.function}).insert()

		self.assertIn(own.name, frappe.get_list(SIGN_UP, pluck="name"))
		self.assertTrue(frappe.has_permission(SIGN_UP, "write", doc=own.name))

	def test_staff_still_read_every_record_of_their_church(self):
		mine = make_pledge(self.campaign_a, self.person).name
		theirs = make_pledge(self.campaign_a, self.neighbours_person).name
		sign_up = self.sign_up(self.neighbours_person).name

		frappe.set_user(self.finance)
		self.assertLessEqual({mine, theirs}, set(frappe.get_list(PLEDGE, pluck="name")))
		self.assertTrue(frappe.has_permission(PLEDGE, "write", doc=theirs))
		self.assertTrue(frappe.has_permission(SIGN_UP, "read", doc=sign_up))

	def test_a_desk_user_who_is_also_a_member_reads_only_their_own_pledges(self):
		"""Church Staff has no right on Pledge, so its Church User role must not open everyone's giving."""
		user = ensure_user(
			"_test_own_records_staff_member@example.com",
			"OwnRecordsStaff",
			roles=("Church Staff", "Church User"),
		)
		set_user_church(user, self.branch_a)
		own_person = make_person("_Test Own Records", "Staff", church=self.branch_a, user=user).name
		mine = make_pledge(self.campaign_a, own_person).name
		theirs = make_pledge(self.campaign_a, self.neighbours_person).name

		self.assert_reads_only(user, PLEDGE, mine, theirs)
