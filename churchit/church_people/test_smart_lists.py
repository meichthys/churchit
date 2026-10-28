# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people import smart_lists
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import CARD, start_smart_list_cards
from churchit.church_people.report.attendance_count.test_attendance_count import attend, make_attendance_list
from churchit.dashboard import count_people_in_list
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_smart_list,
	make_two_churches,
)


class TestSmartLists(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_a_smart_list_is_a_report_builder_report_on_person(self):
		self.assertTrue(smart_lists.is_smart_list(make_smart_list("_Test Smart People").name))
		self.assertFalse(
			smart_lists.is_smart_list(make_smart_list("_Test Smart Families", ref_doctype="Family").name)
		)
		self.assertFalse(smart_lists.is_smart_list(None))

	def test_the_people_on_a_list_are_the_living_ones_it_matches(self):
		smart_list = make_smart_list("_Test Smart Living").name
		listed = make_person("_Test Smart", "_Test Smart List").name
		make_person("_Test Smart", "Not Listed")
		died = make_person("_Test Smart Died", "_Test Smart List").name
		frappe.db.set_value("Person", died, "is_deceased", 1)

		self.assertEqual(smart_lists.get_people(smart_list, None), [listed])

	def test_another_report_is_refused(self):
		families = make_smart_list("_Test Smart Other", ref_doctype="Family").name
		with self.assertRaisesRegex(frappe.ValidationError, "not a smart list"):
			smart_lists.get_people(families, None)


class TestSmartListChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_list_read_for_one_church_holds_only_its_people(self):
		smart_list = make_smart_list("_Test Smart Branch").name
		mine = make_person("_Test Smart Mine", "_Test Smart List", church=self.branch_a).name
		make_person("_Test Smart Theirs", "_Test Smart List", church=self.branch_b)

		self.assertEqual(smart_lists.get_people(smart_list, self.branch_a), [mine])


class TestLifeEventSmartLists(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def baptize(self, first_name, event_type, date):
		return make_person(
			first_name, "_Test Smart Life Event", life_events=[{"event_type": event_type, "date": date}]
		).name

	def test_a_list_on_a_life_event_and_a_date_range_returns_the_people_it_matches(self):
		baptism = ensure("Life Event Type", {"type": "_Test Smart Baptism"})
		wedding = ensure("Life Event Type", {"type": "_Test Smart Wedding"})
		baptized = self.baptize("_Test Smart Baptized", baptism, "2025-04-20")
		self.baptize("_Test Smart Earlier", baptism, "2024-04-20")
		self.baptize("_Test Smart Married", wedding, "2025-04-20")
		smart_list = make_smart_list(
			"_Test Smart Baptized 2025",
			[
				["Life Event", "event_type", "=", baptism],
				["Life Event", "date", "between", ["2025-01-01", "2025-12-31"]],
			],
		)

		self.assertEqual(smart_lists.get_people(smart_list.name, None), [baptized])

	def test_a_person_with_two_matching_events_is_listed_once(self):
		baptism = ensure("Life Event Type", {"type": "_Test Smart Baptism"})
		person = make_person(
			"_Test Smart Twice",
			"_Test Smart Life Event",
			life_events=[
				{"event_type": baptism, "date": "2025-02-01"},
				{"event_type": baptism, "date": "2025-03-01"},
			],
		).name
		smart_list = make_smart_list("_Test Smart Twice", [["Life Event", "event_type", "=", baptism]])

		self.assertEqual(smart_lists.get_people(smart_list.name, None), [person])


class TestSkillLists(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_list_on_a_skill_holds_the_people_of_the_church_who_have_it(self):
		teaching, mercy = (
			ensure("Skill", {"skill_name": name}) for name in ("_Test Teaching", "_Test Mercy")
		)
		smart_list = make_smart_list("_Test Smart Teachers", [["Person Skill", "skill", "=", teaching]])
		teacher = make_person(
			"_Test Smart", "Teacher", church=self.branch_a, skills=[{"skill": mercy}, {"skill": teaching}]
		)
		make_person("_Test Smart", "Merciful", church=self.branch_a, skills=[{"skill": mercy}])
		make_person("_Test Smart", "Other Teacher", church=self.branch_b, skills=[{"skill": teaching}])

		self.assertEqual(smart_lists.get_people(smart_list.name, self.branch_a), [teacher.name])


class TestAttendanceSmartLists(RollbackEachTest):
	"""A saved Attendance Count, "3 times since 2026-09-01", is a smart list."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def setUp(self):
		super().setUp()
		self.smart_list = make_attendance_list("_Test Three Times", from_date="2026-09-01", min_times=3).name
		self.regular = attend(
			make_person("_Test Count", "Regular").name, ["2026-09-06", "2026-09-13", "2026-09-20"]
		)
		self.twice = attend(
			make_person("_Test Count", "Twice").name, ["2026-08-30", "2026-09-06", "2026-09-13"]
		)

	def test_a_saved_count_holds_the_people_it_shows(self):
		people = smart_lists.get_people(self.smart_list, None)

		self.assertTrue(smart_lists.is_smart_list(self.smart_list))
		self.assertIn(self.regular, people)
		self.assertNotIn(self.twice, people)

	def test_a_saved_copy_of_another_script_report_is_refused(self):
		other = frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "_Test Saved Inactive Members",
				"ref_doctype": "Person",
				"report_type": "Custom Report",
				"reference_report": "Inactive Members",
				"is_standard": "No",
			}
		).insert(ignore_permissions=True)

		self.assertFalse(smart_lists.is_smart_list(other.name))
		self.assertFalse(smart_lists.is_smart_list("Attendance Count"))
		with self.assertRaisesRegex(frappe.ValidationError, "not a smart list"):
			smart_lists.get_people(other.name, None)
		with self.assertRaisesRegex(frappe.ValidationError, "not a smart list"):
			count_people_in_list(other.name)

	def test_a_saved_count_drives_an_email_a_pathway_step_and_a_trigger(self):
		email = frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Three Times",
				"message": "<p>Hello</p>",
				"send_to": "Smart List",
				"smart_list": self.smart_list,
			}
		).insert()
		pathway = frappe.get_doc(
			{
				"doctype": "Pathway",
				"pathway_name": "_Test Three Times",
				"steps": [{"step": "Came Three Times", "smart_list": self.smart_list}],
			}
		).insert()
		workflow = make_workflow(
			"_Test Three Times",
			[("Welcome", None, 1)],
			triggers=[{"trigger": "On Smart List", "value": self.smart_list}],
		).name
		start_smart_list_cards()

		self.assertIn(self.regular, email.get_people())
		self.assertNotIn(self.twice, email.get_people())
		self.assertEqual(pathway.get_steps_done().get(self.regular), {"Came Three Times"})
		self.assertNotIn(self.twice, pathway.get_steps_done())
		carded = frappe.get_all(CARD, filters={"workflow": workflow}, pluck="person")
		self.assertIn(self.regular, carded)
		self.assertNotIn(self.twice, carded)

	def test_a_card_counts_a_person_with_two_matching_rows_once(self):
		baptism = ensure("Life Event Type", {"type": "_Test Smart Baptism"})
		make_person(
			"_Test Smart Card",
			"_Test Smart Card Twice",
			life_events=[
				{"event_type": baptism, "date": "2025-02-01"},
				{"event_type": baptism, "date": "2025-03-01"},
			],
		)
		smart_list = make_smart_list(
			"_Test Smart Card Twice",
			[
				["Life Event", "event_type", "=", baptism],
				["Person", "last_name", "=", "_Test Smart Card Twice"],
			],
		)

		self.assertEqual(count_people_in_list(smart_list.name)["value"], 1)

	def test_the_picker_offers_lists_of_people_and_saved_counts_only(self):
		people = make_smart_list("_Test Pick People").name
		make_smart_list("_Test Pick Families", ref_doctype="Family")
		make_attendance_list("_Test Pick Count", from_date="2026-09-01")

		offered = [
			row[0] for row in smart_lists.search_smart_lists("Report", "_Test Pick", "name", 0, 20, {})
		]

		self.assertEqual(offered, ["_Test Pick Count", people])

	def test_the_picker_offers_a_portal_member_nothing(self):
		frappe.set_user(ensure_user("_test_pick_member@example.com", "Pick"))
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaises(frappe.PermissionError):
			smart_lists.search_smart_lists("Report", "_Test Pick", "name", 0, 20, {})

	def test_its_number_card_refuses_a_reader_who_cannot_open_attendance_count(self):
		frappe.set_user(
			ensure_user("_test_count_check_in@example.com", "CountCheckIn", roles=("Church Check-In",))
		)
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaises(frappe.PermissionError):
			count_people_in_list(self.smart_list)


class TestAttendanceSmartListChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_b = ensure_user("_test_count_list_b@example.com", "CountListB", roles=("Church Manager",))
		make_person("CountListB", "Manager", church=cls.branch_b, user=cls.manager_b)

	def setUp(self):
		super().setUp()
		self.smart_list = make_attendance_list("_Test Count Churches", from_date="2026-09-01").name
		self.in_a = make_person("_Test Count", "In A", church=self.branch_a).name
		attend(self.in_a, ["2026-09-06"], church=self.branch_a)
		self.in_b = make_person("_Test Count", "In B", church=self.branch_b).name
		attend(self.in_b, ["2026-09-06"], church=self.branch_b)

	def test_a_list_read_for_one_church_holds_only_its_people(self):
		self.assertEqual(smart_lists.get_people(self.smart_list, self.branch_a), [self.in_a])

	def test_its_number_card_counts_only_the_readers_churches(self):
		frappe.set_user(self.manager_b)
		self.addCleanup(frappe.set_user, "Administrator")
		card = count_people_in_list(self.smart_list)
		people = smart_lists.get_report_people(frappe.get_doc("Report", self.smart_list))

		self.assertIn(self.in_b, people)
		self.assertNotIn(self.in_a, people)
		self.assertEqual(card["value"], len(people))
		self.assertEqual(card["route"], ["query-report", self.smart_list])

	def test_a_saved_church_does_not_widen_the_list(self):
		saved_a = make_attendance_list(
			"_Test Count Saved A", from_date="2026-09-01", church=self.branch_a
		).name

		self.assertEqual(smart_lists.get_people(saved_a, self.branch_b), [])
		frappe.set_user(self.manager_b)
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			smart_lists.get_people(saved_a, self.branch_b)
