# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate, today

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import CHURCH_NEWS
from churchit.church_people.household import ADULT, CHILD
from churchit.church_people.list_actions import (
	get_household_adult_emails,
	get_household_emails,
	get_people_emails,
	mark_inactive,
	new_church_email,
)
from churchit.church_people.membership import ACTIVE, INACTIVE
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_address,
	make_person,
	make_primary_contact,
	make_two_churches,
	set_private_people,
)


def emails(*addresses):
	return [{"email_address": address} for address in addresses]


def make_family(family_name, **values):
	return frappe.get_doc({"doctype": "Family", "family_name": family_name, **values}).insert(
		ignore_permissions=True
	)


def set_roles(family, roles):
	"""Give each member of *family* its household role from *roles* ({person: role})."""
	doc = frappe.get_doc("Family", family)
	for member in doc.members:
		member.household_role = roles.get(member.member, member.household_role)
	doc.save(ignore_permissions=True)


def title(person):
	return frappe.db.get_value("Person", person, "full_name")


class TestListEmails(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.family = make_family("_Test List Household").name
		cls.father = make_primary_contact(
			make_person(
				"_Test List", "Father", family=cls.family, emails=emails("_test_list_father@example.com")
			)
		).name
		cls.mother = make_person("_Test List", "Mother", family=cls.family).name
		cls.son = make_person(
			"_Test List", "Son", family=cls.family, emails=emails("_test_list_son@example.com")
		).name
		set_roles(cls.family, {cls.father: ADULT, cls.mother: ADULT, cls.son: CHILD})
		cls.loner = make_person("_Test List", "Loner").name

	def test_people_emails_list_each_address_once_and_who_has_none(self):
		result = get_people_emails([self.father, self.mother, self.son, self.father])

		self.assertEqual(result.emails, ["_test_list_father@example.com", "_test_list_son@example.com"])
		self.assertEqual(result.without_email, [title(self.mother)])
		self.assertEqual(result.refused, [])

	def test_someone_who_refused_every_email_is_left_out_and_named(self):
		record([self.son], EMAIL, WITHDRAWN)
		record([self.father], EMAIL, WITHDRAWN, CHURCH_NEWS)

		result = get_people_emails([self.father, self.son])

		self.assertEqual(result.emails, ["_test_list_father@example.com"])
		self.assertEqual(result.refused, [title(self.son)])

	def test_a_household_adult_who_refused_every_email_is_left_out_and_named(self):
		record([self.father], EMAIL, WITHDRAWN)

		result = get_household_adult_emails([self.son])

		self.assertEqual(result.emails, [])
		self.assertEqual(result.refused, [title(self.father)])
		self.assertEqual(result.without_email, [title(self.mother)])

	def test_the_adults_of_a_childs_household_are_emailed_and_an_adult_with_no_email_named(self):
		result = get_household_adult_emails(frappe.as_json([self.son]))

		self.assertEqual(result.emails, ["_test_list_father@example.com"])
		self.assertEqual(result.without_email, [title(self.mother)])
		self.assertEqual(result.without_adults, [])

	def test_a_household_picked_through_several_people_is_emailed_once(self):
		result = get_household_adult_emails([self.son, self.father, self.mother])

		self.assertEqual(result.emails, ["_test_list_father@example.com"])
		self.assertEqual(result.without_email, [title(self.mother)])

	def test_someone_with_no_household_adult_is_named(self):
		result = get_household_adult_emails([self.loner])

		self.assertEqual((result.emails, result.without_adults), ([], [title(self.loner)]))

	def test_a_household_is_emailed_at_its_own_address_before_its_primary_contacts(self):
		own = make_family("_Test List Own Email", emails=emails("_test_list_home@example.com"))
		contact = make_person(
			"_Test List", "Contact", family=own.name, emails=emails("_test_list_contact@example.com")
		)
		make_primary_contact(contact)
		empty = make_family("_Test List No Email")

		result = get_household_emails([own.name, self.family, empty.name])

		self.assertEqual(result.emails, ["_test_list_home@example.com", "_test_list_father@example.com"])
		self.assertEqual(result.without_email, [frappe.db.get_value("Family", empty.name, "family_name")])


class TestMarkInactive(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.reason = ensure("Inactive Reason", {"reason": "_Test Moved Away"})
		other = ensure("Inactive Reason", {"reason": "_Test Other Reason"})
		cls.active = make_person("_Test Inactive", "Active", membership_status=ACTIVE).name
		cls.inactive = make_person(
			"_Test Inactive", "Already", membership_status=INACTIVE, inactive_reason=other
		).name

	def status(self, person):
		return frappe.db.get_value(
			"Person", person, ["membership_status", "inactive_reason", "inactive_since"], as_dict=True
		)

	def test_active_people_become_inactive_for_the_reason_from_today(self):
		result = mark_inactive([self.active, self.inactive], self.reason)

		self.assertEqual(result, {"marked": 1, "already_inactive": 1})
		self.assertEqual(
			self.status(self.active),
			{
				"membership_status": INACTIVE,
				"inactive_reason": self.reason,
				"inactive_since": getdate(today()),
			},
		)

	def test_someone_already_inactive_keeps_their_reason(self):
		before = self.status(self.inactive)
		mark_inactive([self.inactive], self.reason)

		self.assertEqual(self.status(self.inactive), before)

	def test_an_unknown_reason_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			mark_inactive([self.active], "_Test No Such Reason")

	def test_staff_who_cannot_edit_people_are_refused(self):
		staff = ensure_user("_test_list_staff@example.com", "Staff", roles=("Church Staff",))
		frappe.set_user(staff)

		with self.assertRaises(frappe.PermissionError):
			mark_inactive([self.active], self.reason)
		self.assertEqual(self.status(self.active).membership_status, ACTIVE)


class TestNewChurchEmail(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.people = [make_person("_Test List", f"Chosen {n}").name for n in (1, 2)]

	def test_the_picked_people_start_a_draft_church_email(self):
		email = frappe.get_doc("Church Email", new_church_email(self.people))

		self.assertEqual((email.status, email.send_to), ("Draft", "Chosen People"))
		self.assertEqual([row.person for row in email.people], self.people)

	def test_staff_who_cannot_write_church_emails_are_refused(self):
		frappe.set_user(ensure_user("_test_list_staff@example.com", "Staff", roles=("Church Staff",)))

		with self.assertRaises(frappe.PermissionError):
			new_church_email(self.people)


class TestPortalMember(RollbackEachTest):
	"""A portal member has no list, and is refused even for their own record."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.member = ensure_user("_test_list_portal@example.com", "Portal")
		cls.family = make_family("_Test List Portal Household").name
		cls.person = make_person(
			"_Test List",
			"Portal",
			family=cls.family,
			user=cls.member,
			emails=emails("_test_list_portal@example.com"),
		).name
		cls.reason = ensure("Inactive Reason", {"reason": "_Test Moved Away"})

	def setUp(self):
		super().setUp()
		frappe.set_user(self.member)

	def test_emails_are_refused(self):
		for call in (get_people_emails, get_household_adult_emails, new_church_email):
			with self.assertRaises(frappe.PermissionError):
				call([self.person])
		with self.assertRaises(frappe.PermissionError):
			get_household_emails([self.family])

	def test_marking_inactive_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			mark_inactive([self.person], self.reason)


class TestListActionsAcrossChurches(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_list_manager_a@example.com", "ListA", roles=("Church Manager",))
		make_person("_Test List", "Manager A", church=cls.branch_a, user=cls.manager_a)
		cls.person_b = make_person(
			"_Test List", "Branch B", church=cls.branch_b, emails=emails("_test_list_branch_b@example.com")
		).name
		cls.family = make_family("_Test List Split Household").name
		cls.father_b = make_primary_contact(
			make_person(
				"_Test List",
				"Father B",
				church=cls.branch_b,
				family=cls.family,
				emails=emails("_test_list_father_b@example.com"),
			)
		).name
		cls.child_a = make_person("_Test List", "Child A", church=cls.branch_a, family=cls.family).name
		set_roles(cls.family, {cls.father_b: ADULT, cls.child_a: CHILD})
		cls.reason = ensure("Inactive Reason", {"reason": "_Test Moved Away"})
		cls.addClassCleanup(frappe.clear_cache)

	def as_manager_a(self, call, *args):
		frappe.set_user(self.manager_a)
		try:
			return call(*args)
		finally:
			frappe.set_user("Administrator")

	def test_another_churchs_people_can_be_emailed_while_the_directory_is_shared(self):
		set_private_people(False)

		self.assertEqual(
			self.as_manager_a(get_people_emails, [self.person_b]).emails, ["_test_list_branch_b@example.com"]
		)

	def test_another_churchs_people_are_refused_while_the_directory_is_private(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		for call in (get_people_emails, get_household_adult_emails):
			with self.assertRaises(frappe.PermissionError):
				self.as_manager_a(call, [self.person_b])

	def test_a_household_adult_of_another_church_stays_out_of_a_private_directory(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		result = self.as_manager_a(get_household_adult_emails, [self.child_a])

		self.assertEqual(result.emails, [])
		self.assertEqual(result.without_adults, [title(self.child_a)])

	def test_another_churchs_people_cannot_be_put_on_a_church_email(self):
		set_private_people(False)

		with self.assertRaisesRegex(frappe.ValidationError, "belong to another church"):
			self.as_manager_a(new_church_email, [self.person_b])

	def test_another_churchs_people_cannot_be_marked_inactive(self):
		set_private_people(False)

		with self.assertRaises(frappe.PermissionError):
			self.as_manager_a(mark_inactive, [self.person_b], self.reason)
		self.assertEqual(frappe.db.get_value("Person", self.person_b, "membership_status"), ACTIVE)


class TestMailingLabels(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.country = "United States"
		cls.addClassCleanup(frappe.db.set_default, "country", frappe.db.get_default("country"))
		frappe.db.set_default("country", cls.country)
		home = make_address(
			"_Test List Label Home",
			address_line1="12 <b>Elm</b> St",
			state="IL",
			pincode="62701",
			country=cls.country,
		).name
		cls.family = make_family("_Test List Label Household", addresses=[{"address": home}]).name
		cls.father = make_primary_contact(
			make_person("_Test List <b>Bob</b>", "Label", family=cls.family)
		).name
		cls.mother = make_person("_Test List Ann", "Label", family=cls.family).name
		set_roles(cls.family, {cls.father: ADULT, cls.mother: ADULT})
		abroad = make_address(
			"_Test List Label Abroad", address_line1="1 Rue Haute", city="Lyon", country="France"
		).name
		cls.traveller = make_person("_Test List", "Traveller", addresses=[{"address": abroad}]).name

	def test_a_person_with_no_address_of_their_own_is_labelled_at_their_familys(self):
		html = frappe.get_print("Person", self.mother, "Mailing Label")

		self.assertIn("_Test List Ann Label", html)
		self.assertIn("12 &lt;b&gt;Elm&lt;/b&gt; St", html)
		self.assertIn("Springfield, IL 62701", html)
		self.assertNotIn(self.country, html)

	def test_names_on_a_label_are_escaped(self):
		html = frappe.get_print("Person", self.father, "Mailing Label")

		self.assertIn("&lt;b&gt;Bob&lt;/b&gt;", html)
		self.assertNotIn("<b>Bob", html)

	def test_an_address_abroad_names_its_country(self):
		html = frappe.get_print("Person", self.traveller, "Mailing Label")

		self.assertIn("1 Rue Haute", html)
		self.assertIn("France", html)

	def test_an_address_whose_mail_came_back_is_left_off(self):
		row = frappe.get_doc("Person", self.traveller).addresses[0].name
		frappe.db.set_value("Postal Address", row, "is_returned_mail", 1)
		self.addCleanup(frappe.db.set_value, "Postal Address", row, "is_returned_mail", 0)

		self.assertNotIn("1 Rue Haute", frappe.get_print("Person", self.traveller, "Mailing Label"))

	def test_a_household_label_is_addressed_to_its_adults(self):
		html = frappe.get_print("Family", self.family, "Household Label")

		self.assertIn("_Test List &lt;b&gt;Bob&lt;/b&gt; &amp; _Test List Ann Label", html)
		self.assertIn("Springfield, IL 62701", html)
