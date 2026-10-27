# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people import smart_lists
from churchit.church_people.doctype.follow_up_workflow.test_follow_up_workflow import make_smart_list
from churchit.church_people.summaries.test_serving import make_person_list
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	force_single_church,
	make_person,
	make_two_churches,
)


class TestSmartLists(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_a_smart_list_is_a_report_builder_report_on_person(self):
		self.assertTrue(smart_lists.is_smart_list(make_smart_list("_Test Smart People").name))
		self.assertFalse(smart_lists.is_smart_list(make_smart_list("_Test Smart Families", "Family").name))
		self.assertFalse(smart_lists.is_smart_list(None))

	def test_the_people_on_a_list_are_the_living_ones_it_matches(self):
		smart_list = make_smart_list("_Test Smart Living").name
		listed = make_person("_Test Smart", "_Test Smart List").name
		make_person("_Test Smart", "Not Listed")
		died = make_person("_Test Smart Died", "_Test Smart List").name
		frappe.db.set_value("Person", died, "is_deceased", 1)

		self.assertEqual(smart_lists.get_people(smart_list, None), [listed])

	def test_another_report_is_refused(self):
		families = make_smart_list("_Test Smart Other", "Family").name
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
		smart_list = make_person_list(
			"_Test Smart Baptized 2025",
			[
				["Life Event", "event_type", "=", baptism],
				["Life Event", "date", "between", ["2025-01-01", "2025-12-31"]],
			],
		)

		self.assertEqual(smart_lists.get_people(smart_list.name, None), [baptized])


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
		smart_list = make_person_list("_Test Smart Teachers", [["Person Skill", "skill", "=", teaching]])
		teacher = make_person(
			"_Test Smart", "Teacher", church=self.branch_a, skills=[{"skill": mercy}, {"skill": teaching}]
		)
		make_person("_Test Smart", "Merciful", church=self.branch_a, skills=[{"skill": mercy}])
		make_person("_Test Smart", "Other Teacher", church=self.branch_b, skills=[{"skill": teaching}])

		self.assertEqual(smart_lists.get_people(smart_list.name, self.branch_a), [teacher.name])
