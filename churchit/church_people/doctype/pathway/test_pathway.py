# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.report.pathway_progress.pathway_progress import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	force_single_church,
	make_person,
	make_smart_list,
	make_two_churches,
)


def make_pathway(name="_Test Next Steps", church=None):
	# Each step lists the test people whose middle name holds its mark.
	people = ["Person", "last_name", "=", "_Test Pathway"]
	came_back = make_smart_list(f"{name} Came Back", [people, ["Person", "middle_name", "like", "%1%"]])
	joined = make_smart_list(f"{name} Group", [people, ["Person", "middle_name", "like", "%2%"]])
	return frappe.get_doc(
		{
			"doctype": "Pathway",
			"pathway_name": name,
			"church": church,
			"steps": [
				{"step": "Came Back", "smart_list": came_back.name},
				{"step": "Joined a Group", "smart_list": joined.name},
			],
		}
	).insert()


class TestPathway(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_each_step_needs_a_smart_list_and_its_own_name(self):
		families = make_smart_list("_Test Pathway Families", ref_doctype="Family").name
		with self.assertRaisesRegex(frappe.ValidationError, "Row 1: choose a smart list"):
			frappe.get_doc(
				{
					"doctype": "Pathway",
					"pathway_name": "_Test Bad List",
					"steps": [{"step": "A", "smart_list": families}],
				}
			).insert()

		people = make_smart_list("_Test Pathway People").name
		with self.assertRaisesRegex(frappe.ValidationError, "its own name: A"):
			frappe.get_doc(
				{
					"doctype": "Pathway",
					"pathway_name": "_Test Repeated",
					"steps": [{"step": "A", "smart_list": people}, {"step": "A", "smart_list": people}],
				}
			).insert()

	def test_the_progress_lists_each_person_with_the_steps_done_and_the_next_one(self):
		pathway = make_pathway()
		both = make_person("Both", "_Test Pathway", middle_name="12").name
		first = make_person("First", "_Test Pathway", middle_name="1").name
		skipped = make_person("Skipped", "_Test Pathway", middle_name="2").name
		make_person("None", "_Test Pathway", middle_name="0")

		columns, data, _message, chart, summary = execute({"pathway": pathway.name})

		progress = {
			row["person"]: (row["step_1"], row["step_2"], row["steps_done"], row["next_step"]) for row in data
		}
		self.assertEqual(
			progress,
			{both: (1, 1, 2, "Done"), first: (1, 0, 1, "Joined a Group"), skipped: (0, 1, 1, "Came Back")},
		)
		self.assertEqual(data[0]["person"], both)
		self.assertEqual([column["label"] for column in columns[1:3]], ["Came Back", "Joined a Group"])
		self.assertEqual([item["value"] for item in summary], [2, 2])
		self.assertEqual(chart["data"]["datasets"][0]["values"], [2, 2])

	def test_the_report_needs_a_pathway_the_reader_may_read(self):
		columns, data = execute({})
		self.assertEqual(
			([column["fieldname"] for column in columns], data), (["person", "steps_done", "next_step"], [])
		)
		pathway = make_pathway("_Test Hidden Path")
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			execute({"pathway": pathway.name})


class TestPathwayChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_a_churchs_pathway_counts_only_its_own_people(self):
		pathway = make_pathway("_Test Branch Steps", church=self.branch_a)
		mine = make_person("Mine", "_Test Pathway", middle_name="1", church=self.branch_a).name
		make_person("Theirs", "_Test Pathway", middle_name="1", church=self.branch_b)

		self.assertEqual(pathway.get_steps_done(), {mine: {"Came Back"}})
