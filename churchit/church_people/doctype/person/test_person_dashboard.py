# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, get_timestamp, today

from churchit.church_people.doctype.person.person import get_timeline_data
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


class TestPersonDashboard(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for attendance_type in ("Checked-In", "Absent"):
			ensure("Function Attendance Type", {"type": attendance_type})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Heatmap", "Person").name

	def attend(self, function_name, days_ago, attendance_type="Checked-In", **values):
		function = make_function(function_name, start_date=add_days(today(), -days_ago), **values)
		function.append("attendance", {"person": self.person, "attendance_type": attendance_type})
		function.save(ignore_permissions=True)
		return function

	def test_the_heatmap_counts_the_functions_attended_each_day_of_the_last_year(self):
		self.attend("_Test Heatmap Morning", 3)
		self.attend("_Test Heatmap Evening", 3)
		self.attend("_Test Heatmap Lately", 10)
		self.attend("_Test Heatmap Absent", 20, "Absent")
		self.attend("_Test Heatmap Long Ago", 400)

		self.assertEqual(
			get_timeline_data("Person", self.person),
			{get_timestamp(add_days(today(), -3)): 2, get_timestamp(add_days(today(), -10)): 1},
		)

	def test_a_reader_who_cannot_read_functions_gets_an_empty_heatmap(self):
		self.attend("_Test Heatmap Seen", 5)
		reader = ensure_user("_test_heatmap_reader@example.com", "_Test Reader", roles=("Church Finance",))

		frappe.set_user(reader)
		self.assertEqual(get_timeline_data("Person", self.person), {})

	def test_the_form_dashboard_keeps_the_connections_and_adds_the_heatmap(self):
		frappe.clear_cache(doctype="Person")
		data = frappe.get_meta("Person").get_dashboard_data()

		self.assertTrue(data.heatmap)
		items = {item for group in data.transactions for item in group["items"]}
		self.assertTrue({"Function", "Prayer Request", "Collection", "Follow-up Card"} <= items)


class TestPersonHeatmapScope(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Function Attendance Type", {"type": "Checked-In"})
		cls.manager = ensure_user(
			"_test_heatmap_manager_a@example.com", "ManagerA", roles=("Church Manager",)
		)
		make_person("ManagerA", "Heatmap", church=cls.branch_a, user=cls.manager)

	def test_the_heatmap_shows_only_the_functions_of_the_readers_churches(self):
		person = make_person("_Test Heatmap", "Visitor", church=self.branch_a).name
		for church, days_ago in ((self.branch_a, 2), (self.branch_b, 4)):
			function = make_function(
				f"_Test Heatmap {church}", church=church, start_date=add_days(today(), -days_ago)
			)
			function.append("attendance", {"person": person, "attendance_type": "Checked-In"})
			function.save(ignore_permissions=True)

		frappe.set_user(self.manager)
		self.assertEqual(get_timeline_data("Person", person), {get_timestamp(add_days(today(), -2)): 1})
