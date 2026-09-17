# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.page.check_in.check_in import (
	add_visitor,
	check_in,
	get_check_ins,
	get_station_context,
	search_people,
	undo_check_in,
)
from churchit.tests.helpers import make_function, make_person


class TestCheckInStation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.function = make_function("_Test Station Function", start_date=frappe.utils.today())
		cls.family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Zebrastripe"}).insert(
			ignore_permissions=True
		)
		cls.parent = make_person(
			"Zed",
			"Zebrastripe",
			family=cls.family.name,
			is_head_of_household=1,
			phones=[{"phone_number": "(555) 010-9876", "is_primary": 1}],
		)
		cls.child = make_person("Zoe", "Zebrastripe", family=cls.family.name, photo="/files/zoe.jpg")
		cls.loner = make_person("Zack", "Zebraless")
		frappe.get_single("Check-In Settings").save(ignore_permissions=True)

	def members_of(self, groups):
		return [[m.first_name for m in group["members"]] for group in groups]

	def test_name_search_expands_matches_to_the_whole_family(self):
		groups = search_people("zoe")
		self.assertEqual(self.members_of(groups), [["Zed", "Zoe"]])
		self.assertEqual([m.matched for m in groups[0]["members"]], [False, True])
		self.assertEqual([m.photo for m in groups[0]["members"]], [None, "/files/zoe.jpg"])
		self.assertEqual(groups[0]["family_name"], "_Test Zebrastripe")

	def test_search_matches_every_word_against_name_or_family(self):
		self.assertEqual(self.members_of(search_people("zack zebral")), [["Zack"]])
		self.assertEqual(self.members_of(search_people("zebra")), [["Zack"], ["Zed", "Zoe"]])
		self.assertEqual(self.members_of(search_people("zebrastripe zoe")), [["Zed", "Zoe"]])

	def test_phone_search_ignores_formatting(self):
		self.assertEqual(self.members_of(search_people("5550109876")), [["Zed", "Zoe"]])
		self.assertEqual(self.members_of(search_people("010-98")), [["Zed", "Zoe"]])

	def test_short_queries_return_nothing(self):
		self.assertEqual(search_people("z"), [])
		self.assertEqual(search_people("  "), [])

	def test_station_context_lists_functions_around_today(self):
		context = get_station_context()
		self.assertIn(self.function.name, [f.name for f in context["functions"]])
		self.assertEqual(context["name_tag_printing"], "Browser")

	def test_check_in_records_people_and_returns_a_print_job(self):
		result = check_in(self.function.name, [self.parent.name, self.child.name], print_tags=1)
		self.assertEqual(len(result["check_ins"]), 2)
		self.assertEqual(result["print"]["count"], 2)
		roster = get_check_ins(self.function.name)
		self.assertEqual(sorted(row.full_name for row in roster), ["Zed Zebrastripe", "Zoe Zebrastripe"])

	def test_check_in_without_printing_returns_no_job(self):
		result = check_in(self.function.name, [self.loner.name])
		self.assertNotIn("print", result)

	def test_undo_removes_the_check_in_and_attendance(self):
		name = check_in(self.function.name, [self.loner.name])["check_ins"][0]
		undo_check_in(name)
		self.assertFalse(frappe.db.exists("Function Check-In", name))
		attendance = frappe.get_doc("Function", self.function.name).attendance
		self.assertNotIn(self.loner.name, [row.person for row in attendance])

	def test_add_visitor_creates_a_person_with_a_phone(self):
		visitor = add_visitor("Zelda", "Zebrastripe", phone="555 010 1111", family=self.family.name)
		person = frappe.get_doc("Person", visitor["name"])
		self.assertEqual(person.full_name, "Zelda Zebrastripe")
		self.assertEqual(person.family, self.family.name)
		self.assertEqual(person.phones[0].phone_number, "555 010 1111")
		self.assertEqual(self.members_of(search_people("0101111")), [["Zed", "Zelda", "Zoe"]])
		person.delete()
