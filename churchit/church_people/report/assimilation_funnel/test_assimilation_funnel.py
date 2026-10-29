# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, today

from churchit.church_people.report.assimilation_funnel.assimilation_funnel import execute
from churchit.church_people.summaries import refresh
from churchit.church_people.test_membership import forget_milestones, keep_milestone
from churchit.tests.helpers import RollbackEachTest, ensure, make_function, make_person

FIRST_VISIT = add_days(today(), -100)


class TestAssimilationFunnel(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Function Attendance Type", {"type": "Checked-In"})
		cls.alice = make_person("_Test Funnel", "Alice").name
		cls.bob = make_person("_Test Funnel", "Bob").name
		cls.carol = make_person("_Test Funnel", "Carol").name
		cls.dave = make_person("_Test Funnel", "Dave").name
		cls.attend(cls.alice, 0, 14)
		cls.attend(cls.bob, 0, 70)
		cls.attend(cls.carol, -30, 0)
		cls.attend(cls.dave, 0)
		frappe.db.set_value("Person", cls.dave, "is_deceased", 1)
		refresh([cls.alice, cls.bob, cls.carol, cls.dave])
		frappe.db.set_value("Person", cls.alice, "group_count", 1)
		forget_milestones(cls.alice)
		keep_milestone(cls.alice, "membership", "Member", f"{add_days(FIRST_VISIT, 30)} 10:00:00")

	@classmethod
	def attend(cls, person, *days_after_first_visit):
		for days in days_after_first_visit:
			function = make_function(f"_Test Funnel {person} {days}", start_date=add_days(FIRST_VISIT, days))
			function.append("attendance", {"person": person, "attendance_type": "Checked-In"})
			function.save(ignore_permissions=True)

	def run_report(self, **filters):
		filters = {"from_date": add_days(FIRST_VISIT, -5), "to_date": add_days(FIRST_VISIT, 5), **filters}
		_columns, data, _message, chart, summary = execute(filters)
		ours = {self.alice, self.bob, self.carol, self.dave}
		rows = {
			row.person: (row.came_back, row.connected, row.became_member)
			for row in data
			if row.person in ours
		}
		return rows, chart, summary

	def test_each_first_visitor_is_listed_with_the_steps_they_reached(self):
		rows, _chart, _summary = self.run_report(weeks=8)

		self.assertEqual(rows, {self.alice: (1, 1, 1), self.bob: (0, 0, 0)})

	def test_coming_back_counts_within_the_weeks_asked_for(self):
		rows, _chart, _summary = self.run_report(weeks=12)

		self.assertEqual(rows[self.bob], (1, 0, 0))

	def test_the_chart_and_summary_count_the_people_at_each_step(self):
		rows, chart, summary = self.run_report(weeks=8)
		counts = chart["data"]["datasets"][0]["values"]

		self.assertEqual(len(counts), 4)
		self.assertEqual([card["value"] for card in summary], counts)
		self.assertGreaterEqual(counts[0], len(rows))
