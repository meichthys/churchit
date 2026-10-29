# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import add_days, getdate

from churchit.church_people.group_meetings import get_meets
from churchit.patches.v1_0 import move_group_associations_to_function_group
from churchit.tests.helpers import (
	RollbackEachTest,
	make_address,
	make_function,
	make_person,
	make_two_churches,
)


def make_group(name, **values):
	return frappe.get_doc({"doctype": "Group", "group_name": name, **values}).insert(ignore_permissions=True)


def add_association(function, association_type, association):
	"""An association row written straight to the table, as rows made before Function.group are."""
	frappe.get_doc(
		{
			"doctype": "Function Association",
			"parenttype": "Function",
			"parentfield": "associations",
			"parent": function.name,
			"idx": len(frappe.get_all("Function Association", filters={"parent": function.name})) + 1,
			"association_type": association_type,
			"association": association,
		}
	).db_insert()


class TestGetMeets(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.group = make_group("_Test Meets Group")

	def make_schedule(self, **values):
		rule = {"repeat_frequency": "Weekly", "repeat_day_of_week": "Tuesday", "start_time": "19:00:00"}
		return make_function(
			"_Test Group Schedule", group=self.group.name, auto_repeat=1, **{**rule, **values}
		)

	def test_a_group_with_no_schedule_has_no_meets(self):
		make_function("_Test One Off Meeting", group=self.group.name)

		self.assertEqual(get_meets(self.group.name), "")
		self.assertEqual(get_meets(None), "")

	def test_meets_names_the_day_the_time_and_the_place(self):
		self.make_schedule(address=make_address("_Test Main Hall").name)

		self.assertEqual(get_meets(self.group.name), "Weekly on Tuesday at 7:00 PM, _Test Main Hall")

	def test_meets_describes_other_rules(self):
		schedule = self.make_schedule(
			repeat_frequency="Monthly", repeat_monthly_by="Weekday", repeat_week_of_month="Second"
		)
		self.assertEqual(get_meets(self.group.name), "Monthly on the Second Tuesday at 7:00 PM")

		schedule.update({"repeat_frequency": "Weekly", "repeat_interval": 2, "all_day": 1})
		schedule.save(ignore_permissions=True)
		self.assertEqual(get_meets(self.group.name), "Every 2 weeks on Tuesday")

	def test_an_ended_schedule_is_left_out(self):
		self.make_schedule(start_date=add_days(getdate(), -30), repeat_until=add_days(getdate(), -1))

		self.assertEqual(get_meets(self.group.name), "")

	def test_the_group_form_shows_the_schedule_as_it_is_now(self):
		schedule = self.make_schedule()
		schedule.repeat_day_of_week = "Thursday"
		schedule.save(ignore_permissions=True)

		group = frappe.get_doc("Group", self.group.name)
		group.run_method("onload")

		self.assertEqual(group.meets, "Weekly on Thursday at 7:00 PM")


class TestMoveGroupAssociations(RollbackEachTest):
	def test_the_first_group_row_moves_into_the_group_field(self):
		group = make_group("_Test Moved Group")
		function = make_function("_Test Moved Function")
		add_association(function, "Group", group.name)

		move_group_associations_to_function_group.execute()

		function.reload()
		self.assertEqual(function.group, group.name)
		self.assertEqual(function.associations, [])

	def test_other_rows_stay_and_a_comment_names_the_kept_group_rows(self):
		first, second = make_group("_Test First Group"), make_group("_Test Second Group")
		person = make_person("_Test Associated")
		function = make_function("_Test Two Groups")
		add_association(function, "Person", person.name)
		add_association(function, "Group", first.name)
		add_association(function, "Group", second.name)

		move_group_associations_to_function_group.execute()
		move_group_associations_to_function_group.execute()

		function.reload()
		self.assertEqual(function.group, first.name)
		self.assertEqual(
			[(row.association_type, row.association) for row in function.associations],
			[("Person", person.name), ("Group", second.name)],
		)
		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Function", "reference_name": function.name},
			pluck="content",
		)
		self.assertEqual(len(comments), 1)
		self.assertIn(second.name, comments[0])

	def test_a_group_of_another_church_stays_an_association(self):
		_root, church_a, church_b = make_two_churches()
		theirs = make_group("_Test Their Group", church=church_b)
		function = make_function("_Test Our Schedule", church=church_a)
		add_association(function, "Group", theirs.name)

		move_group_associations_to_function_group.execute()

		function.reload()
		self.assertFalse(function.group)
		self.assertEqual([row.association for row in function.associations], [theirs.name])

	def test_a_function_with_a_group_already_is_left_alone(self):
		kept, other = make_group("_Test Set Group"), make_group("_Test Other Group")
		function = make_function("_Test Already Grouped", group=kept.name)
		add_association(function, "Group", other.name)

		move_group_associations_to_function_group.execute()

		function.reload()
		self.assertEqual(function.group, kept.name)
		self.assertEqual([row.association for row in function.associations], [other.name])
