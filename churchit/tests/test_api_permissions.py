# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A REST caller meets the refusals the desk shows, on the doctypes whose permission hooks decide access.

Each test signs in as the user a caller would be and makes the calls `/api/resource` makes in
`frappe.api.v1`: `read_doc` (GET one, `get_doc` and `check_permission`), `document_list` (GET a
list, `frappe.client.get_list`) and `update_doc` (PUT). An update loads the record with no check,
applies whatever the caller sent and saves it, so the hooks see the caller's values; a refused
update must not save, and a saved one returns the whole record.
"""

import json
from unittest.mock import patch

import frappe
from frappe.api.v1 import document_list, read_doc, update_doc
from frappe.client import get as client_get
from frappe.desk.form.save import savedocs
from frappe.handler import run_doc_method

from churchit.church_finances.doctype.budget import budget
from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import CARD, add_card
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

PRAYER = "Prayer Request"
PERSON = "Person"
FAMILY = "Family"


class RestTestCase(RollbackEachTest):
	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def rest_read(self, doctype, name):
		frappe.local.form_dict = frappe._dict()
		return read_doc(doctype, name)

	def rest_list(self, doctype, names) -> set[str]:
		frappe.local.form_dict = frappe._dict(filters=json.dumps([["name", "in", names]]), limit=100)
		return {row.name for row in document_list(doctype)}

	def assert_cannot_open(self, doctype, name):
		for read in (self.rest_read, client_get):
			with self.assertRaises(frappe.PermissionError, msg=f"{read.__name__} {doctype} {name}"):
				read(doctype, name)

	def run_on_copy(self, user, method, copy):
		"""Run the whitelisted *method* as `frm.call` does, on the document *copy* the browser sends."""
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.response = frappe._dict(docs=[])
		frappe.set_user(user)
		try:
			return run_doc_method(method, docs=frappe.as_json(copy))
		finally:
			del frappe.local.request
			frappe.set_user("Administrator")

	def saves(self, user, doctype, name, data) -> bool:
		"""True when *user* saved *data* over `name` through the REST update; undone either way."""
		frappe.db.savepoint("rest_update")
		frappe.set_user(user)
		frappe.local.form_dict = frappe._dict(data=json.dumps(data))
		try:
			update_doc(doctype, name)
			return True
		except (frappe.PermissionError, frappe.CannotChangeConstantError):
			return False
		finally:
			frappe.set_user("Administrator")
			frappe.db.rollback(save_point="rest_update")


class TestPrayerRequestOverRest(RestTestCase):
	"""Church Prayer Team reads every request but another person's Private one (prayer_access.py).

	Its own DocPerm reads every request and writes none. Church Staff and Church User write their
	own requests only, so they are not readers in the hook's sense.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		cls.private, cls.team = (
			frappe.get_doc(
				{
					"doctype": PRAYER,
					"title": f"_Test REST {visibility}",
					"type": request_type,
					"visibility": visibility,
					"request": "_Test REST request",
				}
			)
			.insert(ignore_permissions=True)
			.name
			for visibility in ("Private", "Prayer Team")
		)
		cls.praying = [
			ensure_user(f"_test_rest_prayer_{key}@example.com", key, roles=(*roles, "Church Prayer Team"))
			for key, roles in (("team", ()), ("staff", ("Church Staff",)), ("member", ("Church User",)))
		]

	def test_the_prayer_team_cannot_open_another_persons_private_request(self):
		for user in self.praying:
			frappe.set_user(user)
			self.assertEqual(self.rest_read(PRAYER, self.team).name, self.team)
			self.assert_cannot_open(PRAYER, self.private)

	def test_the_prayer_team_does_not_list_another_persons_private_request(self):
		for user in self.praying:
			frappe.set_user(user)
			self.assertEqual(self.rest_list(PRAYER, [self.private, self.team]), {self.team}, user)

	def test_the_prayer_team_cannot_update_another_persons_private_request(self):
		"""Not even by sending itself as the owner, which the hook and Frappe's if_owner rights both read.

		Frappe refuses a changed owner in `validate_set_only_once`, after the permission check passed.
		"""
		saved = [
			(user, field)
			for user in self.praying
			for field, value in (
				("request", "_Test changed"),
				("visibility", "Whole Church"),
				("owner", user),
			)
			if self.saves(user, PRAYER, self.private, {field: value})
		]
		self.assertEqual(saved, [], "Prayer team members who saved another person's Private request")
		stored = frappe.db.get_value(PRAYER, self.private, ["owner", "visibility"], as_dict=True)
		self.assertEqual((stored.owner, stored.visibility), ("Administrator", "Private"))


class TestFollowupCardOverRest(RestTestCase):
	"""The follow-up role reaches only the cards assigned to it, by the stored `_assign` (followup.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.caller = ensure_user("_test_rest_caller@example.com", "Caller", roles=("Church Follow-up",))
		other = ensure_user("_test_rest_other_caller@example.com", "Other", roles=("Church Follow-up",))
		workflow = make_workflow("_Test REST Cards", [("Call", None, 1)]).name
		cls.mine = add_card(make_person("_Test REST", "Mine").name, workflow, assignee=cls.caller)
		cls.unassigned = add_card(make_person("_Test REST", "Unassigned").name, workflow)
		cls.theirs = add_card(make_person("_Test REST", "Theirs").name, workflow, assignee=other)

	def test_the_follow_up_role_opens_only_its_own_cards(self):
		frappe.set_user(self.caller)

		self.assertEqual(self.rest_read(CARD, self.mine).name, self.mine)
		for card in (self.unassigned, self.theirs):
			self.assert_cannot_open(CARD, card)

	def test_the_follow_up_role_lists_only_its_own_cards(self):
		frappe.set_user(self.caller)

		self.assertEqual(self.rest_list(CARD, [self.mine, self.unassigned, self.theirs]), {self.mine})

	def test_a_forged_assignment_opens_no_card(self):
		forged = {"_assign": json.dumps([self.caller]), "outcome": "_Test claimed"}
		saved = [
			card for card in (self.unassigned, self.theirs) if self.saves(self.caller, CARD, card, forged)
		]

		self.assertEqual(saved, [], "Cards the follow-up role claimed by sending itself as the assignee")
		self.assertIsNone(frappe.db.get_value(CARD, self.unassigned, "_assign"))


class TestPortalMemberOverRest(RestTestCase):
	"""A portal member reaches their own Person and Children and their own Family (member_access.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		set_adult_age(18)
		cls.family, cls.father, _mother, cls.son, _gran = make_household("_Test REST Household")
		cls.member = link_user(cls.father, "_test_rest_father@example.com")
		cls.other_family, cls.other_father, _mother, cls.other_son, _gran = make_household(
			"_Test REST Neighbours", last_name="Jones"
		)

	def test_a_member_opens_no_other_households_person_or_family(self):
		frappe.set_user(self.member)

		self.assertEqual(self.rest_read(PERSON, self.father).name, self.father)
		for doctype, name in (
			(PERSON, self.other_father),
			(PERSON, self.other_son),
			(FAMILY, self.other_family),
		):
			self.assert_cannot_open(doctype, name)

	def test_a_member_lists_only_their_own_household(self):
		frappe.set_user(self.member)
		people = [self.father, self.son, self.other_father, self.other_son]

		self.assertEqual(self.rest_list(PERSON, people), {self.father, self.son})
		self.assertEqual(self.rest_list(FAMILY, [self.family, self.other_family]), {self.family})

	def test_a_member_cannot_update_another_household(self):
		"""Not even by naming themselves as the person's portal user, which the Person hook reads."""
		attempts = [
			(PERSON, self.other_father, {"alergies": "_Test REST"}),
			(PERSON, self.other_father, {"alergies": "_Test REST", "user": self.member}),
			(PERSON, self.other_son, {"alergies": "_Test REST", "user": self.member}),
			(FAMILY, self.other_family, {"photo": "/files/_test_rest.png"}),
		]
		saved = [attempt for attempt in attempts if self.saves(self.member, *attempt)]

		self.assertEqual(saved, [], "Updates a member made to another household")

	def test_a_member_cannot_change_who_they_are_to_the_church(self):
		changes = {
			"user": ensure_user("_test_rest_someone@example.com", "Someone"),
			"membership": ensure("Membership Type", {"type": "_Test REST Member"}),
			"membership_status": ensure("Member Status", {"status": "_Test REST Status"}),
			"inactive_reason": ensure("Inactive Reason", {"reason": "_Test REST Moved"}),
			"family": self.other_family,
			"is_deceased": 1,
		}
		saved = [
			field
			for field, value in changes.items()
			if self.saves(self.member, PERSON, self.father, {field: value})
		]

		self.assertEqual(saved, [], "Fields a member changed on their own Person")
		self.assertTrue(self.saves(self.member, PERSON, self.father, {"alergies": "_Test REST Pollen"}))

	def test_a_member_cannot_run_a_person_method_on_a_forged_copy(self):
		"""`run_doc_method` checks read on the copy the browser sends, where the member named themselves."""
		forged = frappe.get_doc(PERSON, self.other_father).as_dict()
		forged.update(
			user=self.member, emails=[{"email_address": "_test_rest_forged@example.com", "is_primary": 1}]
		)
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test REST Outgoing",
				"email_id": "_test_rest_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		for method in ("invite_to_portal", "new_family_from_person"):
			with self.assertRaises(frappe.PermissionError, msg=method):
				self.run_on_copy(self.member, method, forged)


class TestPortalMemberChurchOverRest(RestTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.member = ensure_user("_test_rest_branch_member@example.com", "Branch")
		cls.person = make_person("_Test REST", "Branch Member", church=cls.branch_a, user=cls.member).name

	def test_a_member_cannot_move_themselves_to_another_church(self):
		self.assertFalse(self.saves(self.member, PERSON, self.person, {"church": self.branch_b}))
		self.assertEqual(frappe.db.get_value(PERSON, self.person, "church"), self.branch_a)
		self.assertTrue(self.saves(self.member, PERSON, self.person, {"alergies": "_Test REST Dust"}))


class TestBudgetProgressOverRest(RestTestCase):
	"""`Budget.get_progress` totals the spending of the budget's own church, as the budget is stored.

	The form calls it with `frm.call`, which sends the form as `docs=`, and Frappe checks read on
	that copy, where an empty church passes every User Permission.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, _branch_b = make_two_churches()
		cls.finance = ensure_user("_test_rest_finance@example.com", "Finance", roles=("Church Finance",))
		make_person("_Test REST", "Finance", church=cls.branch_a, user=cls.finance)
		cls.budget = frappe.get_doc(
			{
				"doctype": "Budget",
				"start_date": "2031-01-01",
				"end_date": "2031-12-31",
				"church": cls.branch_a,
			}
		).insert(ignore_permissions=True)

	def test_a_forged_church_totals_no_other_churchs_spending(self):
		copy = self.budget.as_dict()
		copy.update(church="", include_branches=1)
		with patch.object(budget, "get_expense_totals", wraps=budget.get_expense_totals) as totals:
			try:
				self.run_on_copy(self.finance, "get_progress", copy)
			except frappe.PermissionError:
				pass

		totalled = {
			(call.kwargs.get("church"), call.kwargs.get("include_branches")) for call in totals.call_args_list
		}
		self.assertLessEqual(
			totalled, {(self.branch_a, False)}, "Spending totalled for a church the caller sent"
		)


class TestStoredChurch(RestTestCase):
	"""User Permissions count the church a record is stored in, not the one the caller sends."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_b = ensure_user(
			"_test_rest_stored_church@example.com", "Stored Church", roles=("Church Manager",)
		)
		set_user_church(cls.manager_b, cls.branch_b)

	def location(self, church, **values):
		return (
			frappe.get_doc(
				{"doctype": "Location", "location_name": f"_Test Stored {church}", "church": church, **values}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def collection(self, church):
		fund_name = f"_Test Stored Fund {church}"
		fund = ensure("Fund", {"fund": fund_name}, {"fund": fund_name, "church": church})
		payment_type = ensure("Payment Type", {"type": "_Test Stored Cash"})
		collection = frappe.get_doc(
			{"doctype": "Collection", "date": "2031-02-02", "expected_total": 5, "church": church}
		)
		collection.append("donations", {"amount": 5, "fund": fund, "payment_type": payment_type})
		collection.insert(ignore_permissions=True)
		collection.submit()
		return collection.name

	def test_another_churchs_record_cannot_be_moved_by_naming_my_church(self):
		name = self.location(self.branch_a)

		self.assertFalse(self.saves(self.manager_b, "Location", name, {"church": self.branch_b}))
		self.assertEqual(frappe.db.get_value("Location", name, "church"), self.branch_a)

	def test_my_churchs_and_shared_records_still_save(self):
		mine = self.location(self.branch_b)
		shared = self.location(self.branch_a, is_shared=1)

		self.assertTrue(self.saves(self.manager_b, "Location", mine, {"location_name": "_Test Renamed B"}))
		self.assertTrue(
			self.saves(self.manager_b, "Location", shared, {"location_name": "_Test Renamed Shared"})
		)

	def test_another_churchs_record_cannot_be_cancelled_through_a_copy(self):
		"""The desk's Cancel sends the whole document, so Frappe checks cancel on the church in that copy."""
		name = self.collection(self.branch_a)
		copy = frappe.get_doc("Collection", name).as_dict()
		copy["church"] = self.branch_b
		frappe.local.response = frappe._dict(docs=[])
		frappe.set_user(self.manager_b)
		try:
			with self.assertRaises(frappe.PermissionError):
				savedocs(frappe.as_json(copy), "Cancel")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Collection", name, "docstatus"), 1)
