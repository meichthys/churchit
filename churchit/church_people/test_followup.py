# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What starts a follow-up card by itself: the triggers on each workflow's Start a Card When table."""

from unittest.mock import patch

import frappe

from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.doctype.follow_up_workflow.test_follow_up_workflow import make_smart_list
from churchit.church_people.followup import (
	CARD,
	CLOSED,
	on_life_event_added,
	on_membership_changed,
	start_check_in_cards,
	start_smart_list_cards,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)


def workflow_on(name, *triggers, **values):
	"""A one-step workflow that starts on each (trigger, value) of *triggers*."""
	rows = [{"trigger": trigger, "value": value} for trigger, value in triggers]
	return make_workflow(name, [("Welcome", None, 1)], triggers=rows, **values).name


def cards_of(person):
	return frappe.get_all(CARD, filters={"person": person}, pluck="workflow", order_by="workflow asc")


def check_in(function, person, **values):
	"""Check *person* in, and return the name of the check-in whose cards the job would start."""
	with patch("frappe.enqueue") as enqueue:
		frappe.get_doc(
			{"doctype": "Function Check-In", "function": function, "person": person, **values}
		).insert(ignore_permissions=True)
	queued = [call for call in enqueue.call_args_list if call.args and call.args[0] is start_check_in_cards]
	return queued[0].kwargs["check_in"] if queued else None


class TestFollowupTriggers(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure("Member Status", {"status": "_Test Followup Active"})
		ensure("Member Status", {"status": "_Test Followup Inactive"})
		ensure("Membership Type", {"type": "_Test Followup Member"})
		ensure("Life Event Type", {"type": "_Test Followup Baptism"})

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Followup", "Person").name

	def test_a_new_member_status_starts_the_workflows_waiting_for_it(self):
		active = workflow_on("_Test Status Active", ("Member Status Becomes", "_Test Followup Active"))
		any_status = workflow_on("_Test Status Any", ("Member Status Becomes", None))
		workflow_on("_Test Status Inactive", ("Member Status Becomes", "_Test Followup Inactive"))
		workflow_on("_Test Type Member", ("Membership Type Becomes", "_Test Followup Member"))

		on_membership_changed(self.person, field="membership_status", old=None, new="_Test Followup Active")

		self.assertEqual(cards_of(self.person), [active, any_status])

	def test_a_new_membership_type_starts_its_workflows_and_a_cleared_one_starts_none(self):
		member = workflow_on("_Test Type Member", ("Membership Type Becomes", "_Test Followup Member"))

		on_membership_changed(self.person, field="membership", old="_Test Followup Member", new=None)
		self.assertEqual(cards_of(self.person), [])

		on_membership_changed(self.person, field="membership", old=None, new="_Test Followup Member")
		self.assertEqual(cards_of(self.person), [member])

	def test_a_life_event_starts_the_workflows_for_its_type(self):
		baptism = workflow_on("_Test Event Baptism", ("Life Event Added", "_Test Followup Baptism"))
		workflow_on("_Test Event Inactive", ("Life Event Added", None), is_active=0)

		on_life_event_added(self.person, event_type="_Test Followup Baptism", date=None)

		card = frappe.get_doc(CARD, {"person": self.person})
		self.assertEqual(card.workflow, baptism)
		self.assertEqual(card.reason, "Life Event Added: _Test Followup Baptism")

	def test_only_a_persons_first_check_in_ever_starts_a_card(self):
		first_time = workflow_on("_Test First Check-In", ("First Check-In", None))
		first = make_function("_Test Followup First Service")
		second = make_function("_Test Followup Second Service")

		started = start_check_in_cards(check_in(first.name, self.person))
		self.assertEqual(
			frappe.db.get_value(CARD, {"name": ("in", started), "workflow": first_time}, "source_type"),
			"Function Check-In",
		)
		self.assertIsNone(check_in(second.name, self.person))

	def test_a_volunteer_check_in_starts_no_card_and_leaves_the_first_check_in_to_come(self):
		first_time = workflow_on("_Test First Check-In", ("First Check-In", None))
		serving = make_function("_Test Followup Serving")
		attending = make_function("_Test Followup Attending")

		self.assertIsNone(check_in(serving.name, self.person, check_in_kind="Volunteer"))
		start_check_in_cards(check_in(attending.name, self.person))
		self.assertIn(first_time, cards_of(self.person))

	def test_a_check_in_starts_only_the_workflows_for_its_function_type(self):
		other = workflow_on(
			"_Test First Check-In Other", ("First Check-In", ensure("Function Type", {"type": "_Test Other"}))
		)
		function = make_function("_Test Followup Service")

		start_check_in_cards(check_in(function.name, self.person))
		self.assertNotIn(other, cards_of(self.person))

	def test_a_smart_list_adds_each_person_once(self):
		smart_list = make_smart_list("_Test Followup Smart List").name
		workflow = workflow_on("_Test Smart List", ("On Smart List", smart_list))
		listed = make_person("_Test Followup", "_Test Smart List").name
		make_person("_Test Followup", "Not Listed")
		died = make_person("_Test Followup Died", "_Test Smart List").name
		frappe.db.set_value("Person", died, "is_deceased", 1)

		start_smart_list_cards()
		start_smart_list_cards()
		self.assertEqual(frappe.get_all(CARD, filters={"workflow": workflow}, pluck="person"), [listed])

		card = frappe.get_doc(CARD, {"person": listed})
		card.status = CLOSED
		card.save()
		start_smart_list_cards()
		self.assertEqual(frappe.db.count(CARD, {"workflow": workflow}), 1)


class TestFollowupTriggerChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()

	def test_a_check_in_at_a_shared_function_starts_the_persons_own_churchs_workflows(self):
		in_a = workflow_on("_Test Shared Check-In A", ("First Check-In", None), church=self.branch_a)
		in_b = workflow_on("_Test Shared Check-In B", ("First Check-In", None), church=self.branch_b)
		person = make_person("_Test Followup", "Guest", church=self.branch_b).name
		function = make_function("_Test Followup Joint Service", church=self.branch_a, is_shared=1)

		start_check_in_cards(check_in(function.name, person))

		self.assertEqual(cards_of(person), [in_b])
		self.assertNotIn(in_a, cards_of(person))

	def test_a_check_in_starts_the_workflows_of_the_church_holding_the_function(self):
		in_a = workflow_on("_Test Branch Check-In A", ("First Check-In", None), church=self.branch_a)
		workflow_on("_Test Branch Check-In B", ("First Check-In", None), church=self.branch_b)
		person = make_person("_Test Followup", "Visitor", church=self.branch_b).name
		function = make_function("_Test Followup Branch Service", church=self.branch_a)

		start_check_in_cards(check_in(function.name, person))

		self.assertEqual(cards_of(person), [in_a])

	def test_a_smart_list_adds_only_the_people_of_the_workflows_church(self):
		smart_list = make_smart_list("_Test Followup Church List").name
		workflow = workflow_on("_Test Church Smart List", ("On Smart List", smart_list), church=self.branch_a)
		mine = make_person("_Test Followup Mine", "_Test Smart List", church=self.branch_a).name
		make_person("_Test Followup Theirs", "_Test Smart List", church=self.branch_b)

		start_smart_list_cards()

		self.assertEqual(frappe.get_all(CARD, filters={"workflow": workflow}, pluck="person"), [mine])
