# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.desk.form.save import savedocs
from frappe.utils import add_days, today

from churchit.church_people import summaries
from churchit.church_people.summaries import attendance, groups
from churchit.church_people.summaries.test_groups import make_group
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	make_function,
	make_person,
	make_team_position,
	make_two_churches,
)


class TestSummaryEngine(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Function Attendance Type", {"type": "Checked-In"})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Summary", "Engine").name

	def queued(self, doc, method="on_update"):
		with mock.patch("frappe.enqueue") as enqueue:
			summaries.on_change(doc, method)
		return enqueue.call_args.kwargs["people"] if enqueue.called else None

	def test_every_area_in_the_package_is_found(self):
		self.assertIn(attendance, summaries.areas())
		self.assertIn(groups, summaries.areas())
		self.assertFalse(
			[area for area in summaries.areas() if area.__name__.split(".")[-1].startswith("test_")]
		)

	def test_each_area_owns_fields_that_exist_on_person(self):
		meta = frappe.get_meta("Person")
		fields = [field for area in summaries.areas() for field in area.FIELDS]
		self.assertEqual(sorted(set(fields)), sorted(fields), "two areas claim one field")
		self.assertEqual([field for field in fields if not meta.has_field(field)], [])
		self.assertEqual([field for field in fields if not meta.get_field(field).read_only], [])

	def test_saving_a_source_record_queues_its_people(self):
		function = make_function("_Test Queued", start_date=today())
		function.append("attendance", {"person": self.person, "attendance_type": "Checked-In"})

		self.assertEqual(self.queued(function), [self.person])

	def test_a_record_no_area_reads_queues_nothing(self):
		self.assertIsNone(self.queued(frappe.get_doc({"doctype": "ToDo", "description": "_Test summaries"})))

	def test_patches_queue_nothing(self):
		function = make_function("_Test In Patch", start_date=today())
		function.append("attendance", {"person": self.person, "attendance_type": "Checked-In"})
		with mock.patch.dict(frappe.flags, {"in_patch": True}):
			self.assertIsNone(self.queued(function))

	def test_refresh_leaves_modified_alone_and_clears_what_is_gone(self):
		function = make_function("_Test Refresh", start_date=add_days(today(), -1))
		function.append("attendance", {"person": self.person, "attendance_type": "Checked-In"})
		function.save(ignore_permissions=True)
		modified = frappe.db.get_value("Person", self.person, "modified")

		summaries.refresh([self.person])
		self.assertEqual(frappe.db.get_value("Person", self.person, "times_attended_90d"), 1)
		self.assertEqual(frappe.db.get_value("Person", self.person, "modified"), modified)

		function.delete(ignore_permissions=True)
		summaries.refresh([self.person])
		self.assertIsNone(frappe.db.get_value("Person", self.person, "last_attended_on"))

	def test_deleting_a_record_a_summary_names_deletes_its_rows_before_the_refresh(self):
		group = make_group("_Test Summary Deleted", [self.person]).name
		position = make_team_position("_Test Summary Deleted", [self.person], "_Test Summary Ministry")
		summaries.refresh([self.person])

		with mock.patch("frappe.enqueue"):
			frappe.delete_doc("Group", group)
			frappe.delete_doc("Ministry Team Position", position.name)
		frappe.get_doc("Person", self.person).save(ignore_permissions=True)

		self.assertFalse(frappe.db.exists("Person Group", {"parent": self.person}))
		self.assertFalse(frappe.db.exists("Person Team Position", {"parent": self.person}))
		self.assertTrue(frappe.db.exists("Person Ministry Team", {"ministry": position.ministry}))

	def test_a_form_opened_before_a_refresh_saves_without_undoing_it(self):
		"""A refresh leaves `modified` alone, so Frappe takes the older form for the latest copy."""
		opened = frappe.get_doc("Person", self.person).as_dict()
		function = make_function("_Test Stale", start_date=add_days(today(), -1))
		function.append("attendance", {"person": self.person, "attendance_type": "Checked-In"})
		function.save(ignore_permissions=True)
		group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Stale Group", "members": [{"person": self.person}]}
		).insert(ignore_permissions=True)
		summaries.refresh([self.person])

		opened.nickname = "_Test Stale Form"
		savedocs(frappe.as_json(opened), "Save")

		person = frappe.get_doc("Person", self.person)
		self.assertEqual(person.nickname, "_Test Stale Form")
		self.assertEqual((person.times_attended_90d, person.group_count), (1, 1))
		self.assertEqual([row.group for row in person.groups], [group.name])


class TestSummariesStayInTheirChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure("Function Attendance Type", {"type": "Checked-In"})
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def attend(self, person, church, **values):
		function = make_function(f"_Test {church}", start_date=add_days(today(), -1), church=church, **values)
		function.append("attendance", {"person": person, "attendance_type": "Checked-In"})
		function.save(ignore_permissions=True)

	def test_another_churchs_records_do_not_count_but_shared_ones_do(self):
		"""The directory is shared, so a stored figure must not show what a person did at another church."""
		person = make_person("_Test Branch", "Attender", church=self.branch_a).name
		self.attend(person, self.branch_b)
		summaries.refresh([person])
		self.assertEqual(frappe.db.get_value("Person", person, "times_attended_90d"), 0)

		self.attend(person, self.branch_b, is_shared=1)
		summaries.refresh([person])
		self.assertEqual(frappe.db.get_value("Person", person, "times_attended_90d"), 1)
