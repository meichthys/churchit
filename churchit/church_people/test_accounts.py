# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.permissions import add_user_permission

from churchit.church_foundations.church_access import set_user_church, user_church_permissions
from churchit.church_people.accounts import PORTAL, link_portal_user
from churchit.church_people.doctype.people_settings.people_settings import SHARE_DEFAULTS
from churchit.church_people.matching import is_paired
from churchit.church_people.membership import VISITOR
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

MEMBER = "_test_accounts_member@example.com"


def share_in_the_directory_by_default(case):
	"""Turn on every People Settings default for what a new person shares in the member directory."""
	settings = frappe.get_single("People Settings")
	settings.update(dict.fromkeys(SHARE_DEFAULTS.values(), 1))
	settings.save()
	# The rollback removes the Property Setters, not the Person meta cached with them.
	case.addCleanup(frappe.clear_cache, doctype="Person")
	case.assertEqual(frappe.new_doc("Person").share_email, 1)


class TestPortalAccounts(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Membership Type", {"type": VISITOR})

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("People Settings", "match_threshold", 80)
		self.member = ensure_user(MEMBER, "Accounts")
		frappe.db.set_value("User", self.member, "last_name", "_Test Member")
		# The member signed up on branch A's page.
		set_user_church(self.member, self.branch_a)

	def sign_in(self, user=MEMBER):
		frappe.set_user(user)
		try:
			link_portal_user()
		finally:
			frappe.set_user("Administrator")

	def holder(self, first_name, church, email=MEMBER, last_name="_Test Accounts", **values):
		return make_person(first_name, last_name, church=church, emails=[{"email_address": email}], **values)

	def person_of(self, user=MEMBER):
		return frappe.db.get_value("Person", {"user": user}, "name")

	def test_the_one_person_holding_the_address_is_linked(self):
		person = self.holder("Holder", self.branch_a)

		self.sign_in()

		self.assertEqual(self.person_of(), person.name)
		self.assertEqual(frappe.db.count("Person", {"user": MEMBER}), 1)

	def test_a_linked_login_follows_the_persons_church(self):
		"""Linking keeps the church permission rule: the user sees the church of their person."""
		frappe.db.delete("User Permission", {"user": MEMBER, "allow": "Church"})
		add_user_permission(
			"Church", self.root, MEMBER, ignore_permissions=True, is_default=1, hide_descendants=0
		)
		person = self.holder("Branch", self.branch_a)

		self.sign_in()

		self.assertEqual(self.person_of(), person.name)
		self.assertEqual([row.for_value for row in user_church_permissions(MEMBER)], [self.branch_a])

	def test_a_person_with_a_login_or_outside_the_users_churches_is_not_linked(self):
		other = ensure_user("_test_accounts_other@example.com", "Other")
		self.holder("Taken", self.branch_a, user=other)
		elsewhere = self.holder("Elsewhere", self.branch_b, email="_test_accounts_elsewhere@example.com")
		frappe.db.set_value("Email Address", {"parent": elsewhere.name}, "email_address", MEMBER)

		self.sign_in()

		self.assertFalse(frappe.db.get_value("Person", elsewhere.name, "user"))
		self.assertEqual(frappe.db.get_value("Person", {"user": other}, "first_name"), "Taken")

	def test_a_new_login_gets_a_visitor_with_their_names_and_address(self):
		self.sign_in()

		person = frappe.get_doc("Person", self.person_of())
		self.assertEqual(
			(person.first_name, person.last_name, person.membership, person.source, person.church),
			("Accounts", "_Test Member", VISITOR, PORTAL, self.branch_a),
		)
		self.assertEqual([row.email_address for row in person.emails], [MEMBER])

	def test_a_new_login_shares_nothing_in_the_directory(self):
		"""They never saw the choice, whatever People Settings gives a new person."""
		share_in_the_directory_by_default(self)

		self.sign_in()

		shared = frappe.db.get_value("Person", self.person_of(), list(SHARE_DEFAULTS), as_dict=True)
		self.assertEqual(shared, dict.fromkeys(SHARE_DEFAULTS, 0))

	def test_a_new_visitor_shares_an_address_held_elsewhere_and_is_paired_with_its_holder(self):
		"""Only a primary address links; one held as a second address is someone the office should check."""
		namesake = make_person(
			"Accounts",
			"_Test Member",
			church=self.branch_a,
			emails=[
				{"email_address": "_test_accounts_namesake@example.com", "is_primary": 1},
				{"email_address": MEMBER},
			],
		)

		self.sign_in()

		person = frappe.get_doc("Person", self.person_of())
		self.assertNotEqual(person.name, namesake.name)
		self.assertEqual(person.emails[0].shared_from, namesake.name)
		self.assertTrue(is_paired(person.name, namesake.name))

	def test_several_people_holding_the_address_are_paired_and_none_is_linked(self):
		first = self.holder("Twice", self.branch_a)
		second = make_person("Twice", "_Test Accounts", church=self.branch_a)
		# Saved before an address could sit on one person only.
		frappe.get_doc(
			{
				"doctype": "Email Address",
				"parent": second.name,
				"parenttype": "Person",
				"parentfield": "emails",
				"email_address": MEMBER,
				"is_primary": 1,
			}
		).db_insert()

		self.sign_in()

		self.assertIsNone(self.person_of())
		self.assertTrue(is_paired(first.name, second.name))

	def test_staff_administrator_and_guests_are_left_alone(self):
		staff = ensure_user("_test_accounts_staff@example.com", "Staff", roles=("Church Manager",))
		before = frappe.db.count("Person")
		for user in (staff, "Administrator", "Guest"):
			self.sign_in(user)
		self.assertEqual(frappe.db.count("Person"), before)

	def test_a_linked_login_costs_one_query(self):
		self.holder("Linked", self.branch_a, user=self.member)
		frappe.get_cached_value("User", MEMBER, "user_type")
		frappe.set_user(self.member)
		with self.assertQueryCount(1):
			link_portal_user()

	def test_a_link_that_fails_leaves_the_sign_in_alone(self):
		with mock.patch(
			"churchit.church_people.accounts.find_or_add_person", side_effect=frappe.ValidationError
		):
			self.sign_in()
		self.assertIsNone(self.person_of())
		self.assertTrue(frappe.db.exists("Error Log", {"method": ("like", f"%{MEMBER}%")}))

	def test_any_failure_undoes_the_half_made_link_and_leaves_the_sign_in_alone(self):
		holder = self.holder("Half Linked", self.branch_a).name

		def link_then_clash(user):
			frappe.db.set_value("Person", holder, "user", user)
			raise frappe.DuplicateEntryError

		with mock.patch("churchit.church_people.accounts.find_or_add_person", side_effect=link_then_clash):
			self.sign_in()

		self.assertIsNone(self.person_of())
		self.assertTrue(frappe.db.exists("Error Log", {"method": ("like", f"%{MEMBER}%")}))

	def test_a_deadlock_rolls_back_the_transaction_the_database_already_undid(self):
		"""A deadlock takes the savepoint with it, so rolling back to it would fail the sign-in."""
		with (
			mock.patch(
				"churchit.church_people.accounts.find_or_add_person", side_effect=frappe.QueryDeadlockError
			),
			mock.patch.object(frappe.db, "rollback") as rollback,
		):
			self.sign_in()

		rollback.assert_called_once_with()
		self.assertTrue(frappe.db.exists("Error Log", {"method": ("like", f"%{MEMBER}%")}))
