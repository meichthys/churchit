# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import date, time, timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, get_datetime, getdate

from churchit.church_ministries.doctype.function.function import _as_time, apply_template
from churchit.church_ministries.recurrence import create_occurrence
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	make_function,
	make_person,
	make_team_position,
	make_two_churches,
)


class TestFunction(FrappeTestCase):
	def setUp(self):
		self.person = make_person("_Test Function Attendee").name

	def test_title_includes_start_date(self):
		function = make_function("_Test Titled", start_date="2031-05-01")
		self.assertEqual(function.title, "_Test Titled: 2031-05-01")

	def test_attendance_total_counts_only_present_types(self):
		function = make_function("_Test Counted", start_date=getdate())
		for attendance_type in ("Confirmed", "Assumed", "Checked-In", "Absent", "Signed-Up"):
			function.append(
				"attendance",
				{"person": make_person(f"_Test {attendance_type}").name, "attendance_type": attendance_type},
			)
		function.save(ignore_permissions=True)
		self.assertEqual(function.attendance_total, 3)

	def test_apply_template_copies_whitelisted_fields_and_tables(self):
		ministry = ensure("Ministry", {"ministry_name": "_Test Template Ministry"})
		template = make_function(
			"_Test Template",
			description="Weekly gathering",
			all_day=1,
			associated_ministry=ministry,
			publish=1,
		)
		template.append("attendance", {"person": self.person, "attendance_type": "Assumed"})
		template.save(ignore_permissions=True)

		copied = apply_template(template.name)

		self.assertEqual(copied["description"], "Weekly gathering")
		self.assertEqual(copied["all_day"], 1)
		self.assertEqual(copied["associated_ministry"], ministry)
		self.assertEqual([row["person"] for row in copied["attendance"]], [self.person])
		# Only the whitelisted fields travel: dates, publish state and name do not.
		for field in ("function_name", "start_date", "publish", "name"):
			self.assertNotIn(field, copied)

	def test_apply_template_moves_the_schedule_to_the_new_start_date(self):
		template = make_function("_Test Retreat Plan", start_date="2031-05-02", end_date="2031-05-04")
		template.append("schedule", {"description": "Opening", "start": "2031-05-02 19:00:00"})
		template.append(
			"schedule", {"description": "Hike", "start": "2031-05-03 09:00:00", "end": "2031-05-03 12:00:00"}
		)
		template.save(ignore_permissions=True)

		copied = apply_template(template.name, "2031-06-06")

		self.assertEqual(
			[(row["start"], row["end"]) for row in copied["schedule"]],
			[
				(get_datetime("2031-06-06 19:00:00"), None),
				(get_datetime("2031-06-07 09:00:00"), get_datetime("2031-06-07 12:00:00")),
			],
		)

	def test_apply_template_copies_the_team_needs(self):
		position = make_team_position("_Test Template Greeter", [self.person])
		template = make_function(
			"_Test Team Template", team_needs=[{"position": position.name, "quantity": 3}]
		)

		copied = apply_template(template.name)

		self.assertEqual(
			[(row["position"], row["quantity"]) for row in copied["team_needs"]], [(position.name, 3)]
		)

	def test_as_time_accepts_time_timedelta_and_string(self):
		self.assertEqual(_as_time(time(9, 30)), time(9, 30))
		self.assertEqual(_as_time(timedelta(hours=9, minutes=30)), time(9, 30))
		self.assertEqual(_as_time("09:30:00"), time(9, 30))


class TestFunctionGroup(RollbackEachTest):
	def make_group(self, name, **values):
		return frappe.get_doc({"doctype": "Group", "group_name": name, **values}).insert(
			ignore_permissions=True
		)

	def test_an_occurrence_keeps_the_templates_group(self):
		group = self.make_group("_Test Meeting Group")
		template = make_function(
			"_Test Group Template", group=group.name, auto_repeat=1, repeat_frequency="Weekly"
		)

		occurrence = create_occurrence(template, getdate("2031-05-08"))

		self.assertEqual(occurrence.group, group.name)

	def test_another_churches_group_is_refused(self):
		_root, church_a, church_b = make_two_churches()
		group = self.make_group("_Test Church B Group", church=church_b)

		with self.assertRaises(frappe.PermissionError):
			make_function("_Test Church A Meeting", church=church_a, group=group.name)

	def test_a_shared_function_cannot_have_a_group(self):
		group = self.make_group("_Test Shared Group")

		with self.assertRaises(frappe.ValidationError):
			make_function("_Test Shared Meeting", is_shared=1, group=group.name)

	def test_a_new_group_association_row_is_refused(self):
		group = self.make_group("_Test Association Group")
		function = make_function("_Test Associated Function")

		function.append("associations", {"association_type": "Group", "association": group.name})
		with self.assertRaises(frappe.ValidationError):
			function.save(ignore_permissions=True)

	def test_a_new_function_with_a_group_association_row_is_refused(self):
		group = self.make_group("_Test New Association Group")

		with self.assertRaises(frappe.ValidationError):
			make_function(
				"_Test New Associated Function",
				associations=[{"association_type": "Group", "association": group.name}],
			)

	def test_a_kept_group_association_row_saves(self):
		"""The move patch leaves a Function's extra Group rows, and later saves keep them."""
		group = self.make_group("_Test Kept Group")
		function = make_function("_Test Kept Association")
		frappe.get_doc(
			{
				"doctype": "Function Association",
				"parenttype": "Function",
				"parentfield": "associations",
				"parent": function.name,
				"association_type": "Group",
				"association": group.name,
			}
		).db_insert()
		function.reload()

		function.description = "Still saves"
		function.save(ignore_permissions=True)

		self.assertEqual([row.association for row in function.associations], [group.name])


class TestFunctionMeetingLink(RollbackEachTest):
	def test_only_an_https_meeting_link_saves(self):
		function = make_function("_Test Online Meeting", meeting_url="https://meet.example.org/abc")
		self.assertEqual(function.meeting_url, "https://meet.example.org/abc")

		for unsafe in (
			"javascript:alert(1)",
			"http://x.org",
			"https://x.org/a\r\nATTENDEE:mailto:x@example.org",
			"https://x.org/a\nX:1",
			"https://x.org/a b",
			"https://x.org/a\tb",
		):
			function.meeting_url = unsafe
			with self.subTest(unsafe), self.assertRaises(frappe.ValidationError):
				function.save(ignore_permissions=True)

	def test_a_stored_link_is_not_checked_again_on_an_unrelated_save(self):
		function = make_function("_Test Online Old Link", meeting_url="https://meet.example.org/abc")
		frappe.db.set_value("Function", function.name, "meeting_url", "http://old.example.org")

		function.reload()
		function.description = "Now with notes"
		function.save(ignore_permissions=True)
