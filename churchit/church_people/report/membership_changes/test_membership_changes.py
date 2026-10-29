# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.report.membership_changes.membership_changes import execute
from churchit.church_people.test_membership import forget_milestones, keep_milestone
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


class TestMembershipChanges(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.alice = make_person("_Test Changes Alice", church=cls.branch_a).name
		cls.bob = make_person("_Test Changes Bob", church=cls.branch_b).name
		for person in (cls.alice, cls.bob):
			forget_milestones(person)
		keep_milestone(cls.alice, "membership", "Visitor", "2031-03-02 10:00:00")
		keep_milestone(cls.bob, "membership", "Member", "2031-03-10 10:00:00")
		keep_milestone(cls.alice, "membership", "Member", "2031-03-20 10:00:00")
		keep_milestone(cls.alice, "membership_status", "Inactive", "2031-03-21 10:00:00")
		keep_milestone(cls.alice, "membership", "Contact", "2031-04-01 10:00:00")

	def rows(self, **filters):
		_columns, data = execute({"from_date": "2031-03-01", "to_date": "2031-03-31", **filters})
		return [
			(str(row.date), row.person, row.field, row.previous_value, row.value)
			for row in data
			if row.person in (self.alice, self.bob)
		]

	def test_lists_each_change_in_the_range_newest_first_with_the_value_before_it(self):
		self.assertEqual(
			self.rows(),
			[
				("2031-03-21", self.alice, "Status", None, "Inactive"),
				("2031-03-20", self.alice, "Membership", "Visitor", "Member"),
				("2031-03-10", self.bob, "Membership", None, "Member"),
				("2031-03-02", self.alice, "Membership", None, "Visitor"),
			],
		)

	def test_the_field_and_value_filters_narrow_the_changes(self):
		self.assertEqual(
			self.rows(field="membership", value="Member"),
			[
				("2031-03-20", self.alice, "Membership", "Visitor", "Member"),
				("2031-03-10", self.bob, "Membership", None, "Member"),
			],
		)
		self.assertEqual(
			self.rows(field="membership_status"), [("2031-03-21", self.alice, "Status", None, "Inactive")]
		)

	def test_a_church_sees_only_the_changes_of_its_own_people(self):
		self.assertEqual({row[1] for row in self.rows(church=self.branch_a)}, {self.alice})

		manager = ensure_user("_test_changes_manager_b@example.com", "ManagerB", roles=("Church Manager",))
		make_person("ManagerB", "Changes", church=self.branch_b, user=manager)
		frappe.set_user(manager)
		self.assertEqual({row[1] for row in self.rows()}, {self.bob})
