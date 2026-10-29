# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError

from churchit.church_foundations.church_access import set_user_church
from churchit.church_study.doctype.bible_memory_item.bible_memory_item import assign_memory
from churchit.church_study.report.bible_memory.bible_memory import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_person,
	make_translation,
	make_two_churches,
)


def make_group(group_name, church, *people):
	group = frappe.get_doc({"doctype": "Group", "group_name": group_name, "church": church})
	for person in people:
		group.append("members", {"person": person})
	return group.insert(ignore_permissions=True).name


class TestBibleMemoryReport(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.translation = make_translation(cls, "_TBR", [("PSA", 23, 1, "The LORD is my shepherd.")])
		cls.learner_a = ensure_user("_test_report_learner_a@example.com", "_Test Report Learner A")
		cls.learner_b = ensure_user("_test_report_learner_b@example.com", "_Test Report Learner B")
		cls.no_person = ensure_user("_test_report_no_person@example.com", "_Test Report No Person")
		person_a = make_person("_Test Report", "Learner A", user=cls.learner_a, church=cls.branch_a).name
		make_person("_Test Report", "Learner B", user=cls.learner_b, church=cls.branch_b)
		cls.staff_a = ensure_user("_test_report_staff_a@example.com", "Staff A", roles=("Church Staff",))
		set_user_church(cls.staff_a, cls.branch_a)
		cls.staff_b = ensure_user("_test_report_staff_b@example.com", "Staff B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)

		cls.group = make_group("_Test Report Memory Group", cls.branch_a, person_a)
		assign_memory("Psalms 23:1", cls.translation, group=cls.group)
		assign_memory("Psalms 23:2", cls.translation, users=[cls.learner_a, cls.learner_b])
		item = {
			"doctype": "Bible Memory Item",
			"bible_reference": "Psalms 23:2",
			"translation": cls.translation,
		}
		frappe.get_doc({**item, "user": cls.no_person}).insert(ignore_permissions=True)

	def rows(self, **filters):
		_columns, data = execute(filters)
		return sorted(
			(row.user, row.bible_reference, row.group) for row in data if row.translation == self.translation
		)

	def test_a_reader_sees_only_users_of_their_church(self):
		frappe.set_user(self.staff_a)
		self.assertEqual(
			self.rows(),
			[
				(self.learner_a, "Psalms 23:1", self.group),
				(self.learner_a, "Psalms 23:2", None),
			],
		)

	def test_an_unrestricted_reader_keeps_users_with_no_person(self):
		users = {user for user, _reference, _group in self.rows()}
		self.assertEqual(users, {self.learner_a, self.learner_b, self.no_person})

	def test_the_group_filter_lists_only_the_groups_items(self):
		frappe.set_user(self.staff_a)
		self.assertEqual(self.rows(group=self.group), [(self.learner_a, "Psalms 23:1", self.group)])

	def test_a_reader_who_cannot_read_the_group_is_refused(self):
		frappe.set_user(self.staff_b)
		with self.assertRaises(PermissionError):
			self.rows(group=self.group)
