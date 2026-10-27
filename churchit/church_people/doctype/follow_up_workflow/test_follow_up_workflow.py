# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe

from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import CARD_CLOSED, ON_SMART_LIST, STEP_REACHED, VALUE_TYPES, add_card
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)


def board_columns(workflow):
	board = frappe.get_doc(
		"Kanban Board", frappe.db.get_value("Follow-up Workflow", workflow, "kanban_board")
	)
	return [(column.column_name, column.status) for column in board.columns]


def make_smart_list(name, ref_doctype="Person", report_type="Report Builder"):
	return frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": ref_doctype,
			"report_type": report_type,
			"is_standard": "No",
			"json": json.dumps({"filters": [["Person", "last_name", "=", "_Test Smart List"]]}),
		}
	).insert(ignore_permissions=True)


class TestFollowupWorkflow(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_the_board_has_a_column_per_step_and_shows_open_cards_that_are_awake(self):
		workflow = make_workflow("_Test Board", [("Call", None, 1), ("Visit", None, 3)])
		board = frappe.get_doc("Kanban Board", workflow.kanban_board)

		self.assertEqual((board.reference_doctype, board.field_name), ("Follow-up Card", "step"))
		self.assertEqual(board_columns(workflow.name), [("Call", "Active"), ("Visit", "Active")])
		self.assertEqual(
			json.loads(board.filters),
			[
				["Follow-up Card", "workflow", "=", workflow.name],
				["Follow-up Card", "status", "=", "Open"],
				["Follow-up Card", "snoozed_until", "is", "not set"],
			],
		)
		self.assertFalse(board.private)

	def test_the_columns_follow_the_steps_and_a_removed_steps_column_is_archived(self):
		workflow = make_workflow("_Test Board Steps", [("Call", None, 1), ("Visit", None, 3)])
		workflow.steps.reverse()
		workflow.append("steps", {"step": "Lunch"})
		workflow.save()
		self.assertEqual(
			board_columns(workflow.name), [("Visit", "Active"), ("Call", "Active"), ("Lunch", "Active")]
		)

		workflow.steps = [row for row in workflow.steps if row.step != "Call"]
		workflow.save()
		self.assertEqual(
			board_columns(workflow.name), [("Visit", "Active"), ("Lunch", "Active"), ("Call", "Archived")]
		)

		workflow.append("steps", {"step": "Call"})
		workflow.save()
		self.assertEqual(
			board_columns(workflow.name), [("Visit", "Active"), ("Lunch", "Active"), ("Call", "Active")]
		)

	def test_a_step_with_open_cards_cannot_be_removed(self):
		workflow = make_workflow("_Test Board In Use", [("Call", None, 1), ("Visit", None, 3)])
		add_card(make_person("_Test Workflow", "Called").name, workflow.name)
		workflow.steps = [row for row in workflow.steps if row.step != "Call"]

		with self.assertRaisesRegex(frappe.ValidationError, "Move the open cards off Call"):
			workflow.save()

	def test_a_step_name_used_twice_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Used more than once: Call"):
			make_workflow("_Test Board Twice", [("Call", None, 1), ("Call", None, 3)])

	def test_a_step_user_who_cannot_sign_in_is_refused(self):
		user = ensure_user("_test_workflow_disabled@example.com", "Disabled", roles=("Church Follow-up",))
		frappe.db.set_value("User", user, "enabled", 0)

		with self.assertRaisesRegex(frappe.ValidationError, "cannot sign in"):
			make_workflow("_Test Board Disabled", [("Call", user, 1)])

	def test_each_trigger_row_names_what_its_value_is(self):
		before = make_workflow("_Test Board Before", [("Call", None, 1)]).name
		values = {
			ON_SMART_LIST: make_smart_list("_Test Trigger List").name,
			STEP_REACHED: before,
			CARD_CLOSED: before,
		}
		workflow = make_workflow(
			"_Test Board Triggers",
			[("Call", None, 1)],
			triggers=[{"trigger": trigger, "value": values.get(trigger)} for trigger in VALUE_TYPES],
		)

		self.assertEqual({row.trigger: row.value_type for row in workflow.triggers}, VALUE_TYPES)

	def test_a_trigger_value_of_the_wrong_kind_is_refused(self):
		ensure("Member Status", {"status": "_Test Wrong Kind"})

		with self.assertRaises(frappe.LinkValidationError):
			make_workflow(
				"_Test Board Wrong Kind",
				[("Call", None, 1)],
				triggers=[{"trigger": "Life Event Added", "value": "_Test Wrong Kind"}],
			)

	def test_on_smart_list_needs_a_report_builder_list_of_people(self):
		on_family = make_smart_list("_Test Family List", ref_doctype="Family")
		people = make_smart_list("_Test People List")

		for report in (None, on_family.name):
			with self.subTest(report=report), self.assertRaisesRegex(frappe.ValidationError, "smart list"):
				make_workflow(
					f"_Test Board List {report}",
					[("Call", None, 1)],
					triggers=[{"trigger": "On Smart List", "value": report}],
				)
		make_workflow(
			"_Test Board List",
			[("Call", None, 1)],
			triggers=[{"trigger": "On Smart List", "value": people.name}],
		)

	def test_deleting_a_workflow_deletes_its_board(self):
		workflow = make_workflow("_Test Board Deleted", [("Call", None, 1)])

		workflow.delete()

		self.assertFalse(frappe.db.exists("Kanban Board", workflow.kanban_board))


class TestFollowupWorkflowChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.volunteer_b = ensure_user(
			"_test_workflow_volunteer_b@example.com", "VolunteerB", roles=("Church Follow-up",)
		)
		make_person("VolunteerB", "_Test Workflow", church=cls.branch_b, user=cls.volunteer_b)

	def test_a_step_user_who_cannot_see_the_workflows_church_is_refused(self):
		with self.assertRaisesRegex(frappe.PermissionError, "cannot see"):
			make_workflow("_Test Board Branch A", [("Call", self.volunteer_b, 1)], church=self.branch_a)

		make_workflow("_Test Board Branch B", [("Call", self.volunteer_b, 1)], church=self.branch_b)
