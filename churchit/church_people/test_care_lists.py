# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The pastoral care lists: saved Report Builder reports on Person that read the care figures."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from churchit.church_people.test_standard_lists import person, shown, staff_user
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
	set_private_people,
)

CARE_LISTS = ("People with Open Care Requests", "Members Not Seen Lately", "Members by Last Visit")
CARE_ROLES = {"System Manager", "Church Manager", "Church Pastoral Care"}


class TestCareListsAreShipped(FrappeTestCase):
	def test_each_is_a_standard_report_builder_list_on_person_for_pastoral_care(self):
		for report_name in CARE_LISTS:
			report = frappe.get_doc("Report", report_name)
			self.assertEqual(
				(report.is_standard, report.report_type, report.ref_doctype),
				("Yes", "Report Builder", "Person"),
				report_name,
			)
			self.assertEqual({row.role for row in report.roles}, CARE_ROLES, report_name)
			self.assertIn(["Person", "is_deceased", "=", 0], json.loads(report.json)["filters"], report_name)


class TestCareListsPickTheRightPeople(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure("Member Status", {"status": "Active"})
		cls.care = staff_user("care", "Church Pastoral Care")
		cls.staff = staff_user("staff")

	def assert_list(self, report_name, expected, others):
		people = shown(report_name, self.care)
		self.assertEqual([name for name in people if name in {*expected, *others}], expected, report_name)

	def test_people_with_open_care_requests(self):
		waiting = person("_Test Care List", "Waiting", open_care_requests=2)
		helped = person("_Test Care List", "Helped")
		died = person("_Test Care List", "Died", open_care_requests=1, is_deceased=1)

		self.assert_list("People with Open Care Requests", [waiting], [helped, died])

	def test_members_not_seen_lately_attended_before_but_not_in_90_days(self):
		long_ago = add_days(today(), -120)
		missing = person("_Test Care List", "Missing", membership="Member", last_attended_on=long_ago)
		attender = person(
			"_Test Care List", "Attender", membership="Regular Attender", last_attended_on=long_ago
		)
		regular = person(
			"_Test Care List", "Regular", membership="Member", last_attended_on=today(), times_attended_90d=8
		)
		never = person("_Test Care List", "Never", membership="Member")
		died = person(
			"_Test Care List", "Late", membership="Member", last_attended_on=long_ago, is_deceased=1
		)

		self.assert_list("Members Not Seen Lately", [missing], [attender, regular, never, died])

	def test_members_by_last_visit_puts_the_longest_unvisited_first(self):
		never = person("_Test Care List", "Unvisited", membership="Member")
		long_ago = person(
			"_Test Care List", "Long Ago", membership="Member", last_visited_on=add_days(today(), -400)
		)
		recent = person(
			"_Test Care List", "Recent", membership="Member", last_visited_on=add_days(today(), -7)
		)
		visitor = person("_Test Care List", "Visitor", membership="Visitor")
		died = person("_Test Care List", "Gone", membership="Member", is_deceased=1)

		self.assert_list("Members by Last Visit", [never, long_ago, recent], [visitor, died])

	def test_other_staff_cannot_run_them(self):
		for report_name in CARE_LISTS:
			with self.assertRaises(frappe.PermissionError, msg=report_name):
				shown(report_name, self.staff)


class TestCareListsStayInTheChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Member Status", {"status": "Active"})
		cls.care_b = ensure_user(
			"_test_care_lists_b@example.com", "CareB", roles=("Church Staff", "Church Pastoral Care")
		)
		make_person("CareB", "Pastor", church=cls.branch_b, user=cls.care_b)

	def test_a_private_directory_lists_only_the_readers_church(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		theirs = person("_Test Care List", "In A", church=self.branch_a, open_care_requests=1)
		mine = person("_Test Care List", "In B", church=self.branch_b, open_care_requests=1)

		people = shown("People with Open Care Requests", self.care_b)

		self.assertIn(mine, people)
		self.assertNotIn(theirs, people)
