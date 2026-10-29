# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The standard lists: saved Report Builder reports on Person, their number cards, and emailing them."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, getdate, today

from churchit.church_people.number_card.first_time_visitors import first_time_visitors
from churchit.church_people.number_card.inactivity_candidates import inactivity_candidates
from churchit.dashboard import count_people_in_list
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
	set_private_people,
)

STAFF = {"System Manager", "Church Manager", "Church People Editor", "Church Staff"}
ROLES = {
	"Inactivity Candidates": STAFF,
	"First-Time Visitors": STAFF,
	"Not in a Group": STAFF,
	"Children": STAFF,
	"Lapsed Givers": {"System Manager", "Church Manager", "Church Finance"},
	"Background Checks Expiring": {"System Manager", "Church Manager", "Church Pastoral Care"},
}


def saved_filters(report_name):
	return json.loads(frappe.get_doc("Report", report_name).json)["filters"]


def shown(report_name, user):
	"""The people a saved list shows *user*: its own fields, filters and order, as the report view and the email run it."""
	_columns, rows = frappe.get_doc("Report", report_name).get_data(user=user, as_dict=True)
	return [row.name for row in rows]


def person(first_name, last_name, church=None, **summary):
	"""A living adult with an Active status whose summary fields are set straight, as the summary areas would."""
	name = make_person(first_name, last_name, **({"church": church} if church else {})).name
	values = {"is_deceased": 0, "life_stage": "Adult", "membership_status": "Active", **summary}
	frappe.db.set_value("Person", name, values, update_modified=False)
	return name


def staff_user(key, *roles):
	return ensure_user(f"_test_lists_{key}@example.com", key.title(), roles=("Church Staff", *roles))


class TestShippedLists(FrappeTestCase):
	def test_each_list_is_a_standard_report_builder_report_on_person_for_its_roles(self):
		for report_name, roles in ROLES.items():
			report = frappe.get_doc("Report", report_name)
			self.assertEqual(
				(report.is_standard, report.report_type, report.ref_doctype),
				("Yes", "Report Builder", "Person"),
				report_name,
			)
			self.assertEqual({row.role for row in report.roles}, roles, report_name)

	def test_every_list_leaves_out_people_who_have_died(self):
		for report_name in ROLES:
			self.assertIn(["Person", "is_deceased", "=", 0], saved_filters(report_name), report_name)

	def test_a_list_is_offered_only_to_its_roles(self):
		frappe.set_user(staff_user("offered"))
		self.addCleanup(frappe.set_user, "Administrator")

		self.assertTrue(frappe.get_doc("Report", "Inactivity Candidates").is_permitted())
		self.assertFalse(frappe.get_doc("Report", "Lapsed Givers").is_permitted())
		self.assertFalse(frappe.get_doc("Report", "Background Checks Expiring").is_permitted())


class TestListsPickTheRightPeople(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure("Member Status", {"status": "Active"})
		ensure("Member Status", {"status": "Inactive"})
		cls.staff = staff_user("staff")
		cls.finance = staff_user("finance", "Church Finance")
		cls.care = staff_user("care", "Church Pastoral Care")

	def assert_list(self, report_name, user, expected, others):
		people = set(shown(report_name, user))
		self.assertEqual(people & {*expected, *others}, set(expected), report_name)

	def test_inactivity_candidates_attended_before_but_not_in_90_days(self):
		long_ago = add_days(today(), -120)
		lapsed = person("_Test List", "Lapsed", last_attended_on=long_ago)
		regular = person(
			"_Test List", "Regular", last_attended_on=add_days(today(), -7), times_attended_90d=5
		)
		never = person("_Test List", "Never")
		inactive = person("_Test List", "Inactive", last_attended_on=long_ago, membership_status="Inactive")
		died = person("_Test List", "Died", last_attended_on=long_ago, is_deceased=1)

		self.assert_list("Inactivity Candidates", self.staff, [lapsed], [regular, never, inactive, died])

	def test_first_time_visitors_first_attended_in_the_last_30_days(self):
		new = person("_Test List", "New", first_attended_on=add_days(today(), -10))
		earlier = person("_Test List", "Earlier", first_attended_on=add_days(today(), -45))
		never = person("_Test List", "Unseen")
		died = person("_Test List", "Gone", first_attended_on=add_days(today(), -10), is_deceased=1)

		self.assert_list("First-Time Visitors", self.staff, [new], [earlier, never, died])

	def test_not_in_a_group_lists_active_adults_in_no_group(self):
		alone = person("_Test List", "Alone")
		grouped = person("_Test List", "Grouped", group_count=2)
		child = person("_Test List", "Kid", life_stage="Child")
		inactive = person("_Test List", "Away", membership_status="Inactive")
		died = person("_Test List", "Late", is_deceased=1)

		self.assert_list("Not in a Group", self.staff, [alone], [grouped, child, inactive, died])

	def test_children_lists_living_children(self):
		child = person("_Test List", "Child", life_stage="Child")
		adult = person("_Test List", "Adult")
		died = person("_Test List", "Lost", life_stage="Child", is_deceased=1)

		self.assert_list("Children", self.staff, [child], [adult, died])

	def test_lapsed_givers_lists_living_people_whose_giving_lapsed(self):
		lapsed_on = add_days(today(), -120)
		lapsed = person("_Test List", "Lapsed Giver", last_gift_on=lapsed_on, is_lapsed_giver=1)
		current = person("_Test List", "Current Giver", last_gift_on=today())
		died = person("_Test List", "Late Giver", last_gift_on=lapsed_on, is_lapsed_giver=1, is_deceased=1)

		self.assert_list("Lapsed Givers", self.finance, [lapsed], [current, died])

	def test_background_checks_expiring_lists_cleared_checks_due_soon(self):
		def check(last_name, status, days):
			return person(
				"_Test List",
				last_name,
				background_check_status=status,
				background_check_expires_on=add_days(today(), days),
			)

		due = check("Due", "Cleared", 20)
		later = check("Later", "Cleared", 200)
		refused = check("Refused", "Not Cleared", 20)

		self.assert_list("Background Checks Expiring", self.care, [due], [later, refused])


class TestGivingAndCareListsNeedTheirFields(FrappeTestCase):
	"""A Report Builder report's roles only hide the link; the field permlevels are the guard."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.staff = staff_user("staff")
		cls.giver = person("_Test List", "Hidden Giver", last_gift_on=add_years(today(), -1))

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_other_staff_cannot_run_the_lists(self):
		for report_name in ("Lapsed Givers", "Background Checks Expiring"):
			with self.assertRaises(frappe.PermissionError, msg=report_name):
				shown(report_name, self.staff)

	def test_other_staff_get_no_last_gift_column(self):
		frappe.set_user(self.staff)

		rows = frappe.get_list("Person", filters={"name": self.giver}, fields=["name", "last_gift_on"])
		self.assertEqual(rows, [{"name": self.giver}])


class TestListCardsAndEmails(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Member Status", {"status": "Active"})
		cls.manager_b = ensure_user("_test_lists_manager_b@example.com", "ListsB", roles=("Church Manager",))
		make_person("ListsB", "Manager", church=cls.branch_b, user=cls.manager_b)
		long_ago = add_days(today(), -120)
		person("_Test List", "Lapsed In A", church=cls.branch_a, last_attended_on=long_ago)
		person("_Test List", "Lapsed In B", church=cls.branch_b, last_attended_on=long_ago)
		person("_Test List", "New In A", church=cls.branch_a, first_attended_on=today())

	def count(self, card):
		frappe.set_user(self.manager_b)
		try:
			return card.get_count()["value"]
		finally:
			frappe.set_user("Administrator")

	def test_cards_count_only_the_readers_churches(self):
		matching = {
			first_time_visitors: {"first_attended_on": today()},
			inactivity_candidates: {"last_attended_on": add_days(today(), -100)},
		}
		for card, summary in matching.items():
			before = self.count(card)

			person("_Test List", "Counted In A", church=self.branch_a, **summary)
			self.assertEqual(self.count(card), before, card.__name__)

			person("_Test List", "Counted In B", church=self.branch_b, **summary)
			self.assertEqual(self.count(card), before + 1, card.__name__)

	def test_a_card_opens_its_list_narrowed_to_the_readers_churches(self):
		frappe.set_user(self.manager_b)
		card = inactivity_candidates.get_count()

		self.assertEqual(card["route"], ["List", "Person", "Report", "Inactivity Candidates"])
		operator, churches = card["route_options"]["church"]
		self.assertEqual(operator, "in")
		self.assertIn(self.branch_b, churches)
		self.assertNotIn(self.branch_a, churches)

	def test_a_card_refuses_a_reader_the_list_is_not_offered_to(self):
		frappe.set_user(ensure_user("_test_lists_card_staff@example.com", "Card", roles=("Church Staff",)))

		with self.assertRaises(frappe.PermissionError):
			count_people_in_list("Lapsed Givers")

	def test_an_emailed_list_runs_as_its_user_and_skips_an_empty_email(self):
		"""Frappe's Auto Email Report is the subscription; in a private directory it sends only the user's church."""
		set_private_people(True)
		self.addCleanup(set_private_people, False)

		digest = self.auto_email_report("Inactivity Candidates")
		html = digest.get_report_content()
		self.assertIn("Lapsed In B", html)
		self.assertNotIn("Lapsed In A", html)

		empty = self.auto_email_report("First-Time Visitors")
		self.assertTrue(empty.send_if_data)
		self.assertIsNone(empty.get_report_content())
		empty.send()
		self.assertFalse(frappe.db.exists("Email Queue", {"reference_name": empty.name}))

	def auto_email_report(self, report_name):
		return frappe.get_doc(
			{
				"doctype": "Auto Email Report",
				"report": report_name,
				"user": self.manager_b,
				"email_to": self.manager_b,
				"format": "HTML",
				"frequency": "Weekly",
			}
		).insert(ignore_permissions=True)
