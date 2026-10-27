# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What a workflow does by itself when a card opens, reaches a step or closes, and the workflows that start then."""

import inspect
from unittest.mock import patch

import frappe
from frappe.desk.doctype.tag.tag import DocTags

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import (
	ACTION_RUN,
	CARD,
	CARD_CLOSED,
	CARD_OPENED,
	CLOSED,
	STEP_REACHED,
	add_card,
	close_repeated_cards,
	run_actions,
	start_cards,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

STEPS = [("Welcome", None, 1), ("Class", None, 7), ("Done", None, 0)]


def make_template():
	return ensure(
		"Email Template",
		{"name": "_Test Followup Action Template"},
		{
			"doctype": "Email Template",
			"name": "_Test Followup Action Template",
			"subject": "Hello {{ first_name }}",
			"response": "<p>Welcome to {{ step }}</p>",
		},
	)


def make_group(name, **values):
	return (
		frappe.get_doc({"doctype": "Group", "group_name": name, **values})
		.insert(ignore_permissions=True)
		.name
	)


def queued_events(save):
	"""The (event, step) of each run_actions job that *save* queues after its commit.

	frappe.enqueue keeps its own arguments, so the job gets only the others: those must fit run_actions.
	"""
	enqueue_arguments = inspect.signature(frappe.enqueue).parameters
	with patch("frappe.enqueue") as enqueue:
		save()
	events = []
	for call in enqueue.call_args_list:
		if call.args and call.args[0] is run_actions:
			job = inspect.signature(run_actions).bind(
				**{name: value for name, value in call.kwargs.items() if name not in enqueue_arguments}
			)
			events.append((job.arguments["run_on"], job.arguments["step"]))
	return events


def move(card, step=None, status=None):
	doc = frappe.get_doc(CARD, card)
	doc.step = step or doc.step
	doc.status = status or doc.status
	doc.save(ignore_permissions=True)


def runs(card):
	return frappe.get_all(ACTION_RUN, filters={"card": card}, pluck="status", order_by="creation asc")


class TestFollowupActions(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		create_communication_purposes()
		cls.template = make_template()
		cls.unknown_template = ensure(
			"Email Template",
			{"name": "_Test Followup Unknown Template"},
			{
				"doctype": "Email Template",
				"name": "_Test Followup Unknown Template",
				"subject": "{{ group_name }}",
			},
		)
		cls.group = make_group("_Test Followup Action Group")
		ensure("Tag", {"name": "_Test Followup Newcomer"})

	def setUp(self):
		super().setUp()
		self.sendmail = self.enterContext(patch("frappe.sendmail"))
		self.enterContext(patch.object(frappe.db, "commit"))
		self.person = make_person(
			"_Test Followup", "Action", emails=[{"email_address": "_test_followup_action@example.com"}]
		).name

	def workflow(self, *actions, name="_Test Followup Actions"):
		return make_workflow(name, STEPS, actions=list(actions)).name

	def email_on(self, run_on, step=None):
		return {
			"run_on": run_on,
			"step": step,
			"action": "Send Email",
			"purpose": CHURCH_NEWS,
			"email_template": self.template,
		}

	def test_a_card_queues_its_events_only_when_the_workflow_acts_on_them(self):
		workflow = self.workflow(
			self.email_on(CARD_OPENED), self.email_on(STEP_REACHED), self.email_on(CARD_CLOSED)
		)
		quiet = make_workflow("_Test Followup Quiet", STEPS).name

		opened = queued_events(lambda: add_card(self.person, workflow))
		self.assertEqual(opened, [(CARD_OPENED, "Welcome"), (STEP_REACHED, "Welcome")])
		card = frappe.db.get_value(CARD, {"person": self.person, "workflow": workflow})
		self.assertEqual(queued_events(lambda: move(card, "Class")), [(STEP_REACHED, "Class")])
		self.assertEqual(queued_events(lambda: move(card, status=CLOSED)), [(CARD_CLOSED, "Class")])
		self.assertEqual(queued_events(lambda: add_card(self.person, quiet)), [])

	def test_a_step_reached_twice_sends_one_email_linked_to_the_card(self):
		workflow = self.workflow(self.email_on(STEP_REACHED, "Class"))
		card = add_card(self.person, workflow)
		run_actions(card, STEP_REACHED, "Welcome")
		self.assertEqual(runs(card), [])

		move(card, "Class")
		run_actions(card, STEP_REACHED, "Class")
		move(card, "Done")
		move(card, "Class")
		run_actions(card, STEP_REACHED, "Class")

		self.assertEqual(runs(card), ["Done"])
		self.assertEqual(self.sendmail.call_count, 1)
		self.assertIn("Welcome to Class", self.sendmail.call_args.kwargs["message"])
		copies = frappe.get_all(
			"Communication Link",
			filters={"link_doctype": CARD, "link_name": card, "parenttype": "Communication"},
			pluck="parent",
		)
		self.assertEqual(len(copies), 1)
		self.assertEqual(frappe.db.get_value("Communication", copies[0], "reference_name"), self.person)

	def test_withdrawn_consent_logs_skipped(self):
		record([self.person], EMAIL, WITHDRAWN, CHURCH_NEWS)
		card = add_card(self.person, self.workflow(self.email_on(CARD_OPENED)))

		run_actions(card, CARD_OPENED, "Welcome")

		self.assertEqual(runs(card), ["Skipped"])
		self.sendmail.assert_not_called()

	def test_adding_to_a_group_twice_leaves_one_member(self):
		join = {"action": "Add to Group", "group": self.group}
		card = add_card(
			self.person, self.workflow({"run_on": CARD_OPENED, **join}, {"run_on": STEP_REACHED, **join})
		)

		run_actions(card, CARD_OPENED, "Welcome")
		run_actions(card, STEP_REACHED, "Welcome")

		members = frappe.get_all(
			"Group Member", filters={"parent": self.group, "person": self.person}, pluck="name"
		)
		self.assertEqual(len(members), 1)
		self.assertEqual(runs(card), ["Done", "Skipped"])

	def test_a_tag_is_added_once(self):
		tag = {"action": "Add Tag", "tag": "_Test Followup Newcomer"}
		card = add_card(
			self.person, self.workflow({"run_on": CARD_OPENED, **tag}, {"run_on": CARD_CLOSED, **tag})
		)

		run_actions(card, CARD_OPENED, "Welcome")
		run_actions(card, CARD_CLOSED, "Welcome")

		self.assertEqual(DocTags("Person").get_tags(self.person), "_Test Followup Newcomer")
		self.assertEqual(runs(card), ["Done", "Skipped"])

	def test_a_failed_action_is_logged_undone_and_never_retried(self):
		tag = {"run_on": CARD_OPENED, "action": "Add Tag", "tag": "_Test Followup Newcomer"}
		join = {"run_on": CARD_OPENED, "action": "Add to Group", "group": self.group}
		card = add_card(self.person, self.workflow(tag, join))

		refused = frappe.ValidationError("No tag links")
		with (
			patch("frappe.log_error") as log_error,
			patch("frappe.get_doc", side_effect=self.refuse_tag_link(refused)),
		):
			run_actions(card, CARD_OPENED, "Welcome")
		run_actions(card, CARD_OPENED, "Welcome")

		self.assertEqual(runs(card), ["Failed", "Done"])
		self.assertEqual(
			frappe.db.get_value(ACTION_RUN, {"card": card, "status": "Failed"}, "error"), "No tag links"
		)
		self.assertEqual(DocTags("Person").get_tags(self.person), "")
		self.assertEqual(log_error.call_count, 1)

	@staticmethod
	def refuse_tag_link(error):
		get_doc = frappe.get_doc

		def refuse(*args, **kwargs):
			if args and isinstance(args[0], dict) and args[0].get("doctype") == "Tag Link":
				raise error
			return get_doc(*args, **kwargs)

		return refuse

	def test_actions_run_as_the_guest_who_sent_a_connection_card(self):
		card = add_card(
			self.person,
			self.workflow(
				self.email_on(CARD_OPENED),
				{"run_on": CARD_OPENED, "action": "Add to Group", "group": self.group},
				{"run_on": CARD_OPENED, "action": "Add Tag", "tag": "_Test Followup Newcomer"},
			),
		)

		frappe.set_user("Guest")
		run_actions(card, CARD_OPENED, "Welcome")

		self.assertEqual(runs(card), ["Done", "Done", "Done"])
		self.assertEqual(DocTags("Person").get_tags(self.person), "_Test Followup Newcomer")
		self.assertTrue(
			frappe.db.exists(
				"Tag Link",
				{"document_type": "Person", "document_name": self.person, "tag": "_Test Followup Newcomer"},
			)
		)

	def test_a_tag_that_does_not_exist_is_not_added(self):
		workflow = self.workflow(
			{"run_on": CARD_OPENED, "action": "Add Tag", "tag": "_Test Followup Newcomer"}
		)
		card = add_card(self.person, workflow)
		row = frappe.db.get_value("Follow-up Action", {"parent": workflow})
		frappe.db.set_value("Follow-up Action", row, "tag", "_Test Followup Missing")

		with patch("frappe.log_error"):
			run_actions(card, CARD_OPENED, "Welcome")

		self.assertEqual(runs(card), ["Failed"])
		self.assertEqual(DocTags("Person").get_tags(self.person), "")
		self.assertFalse(frappe.db.exists("Tag Link", {"document_name": self.person}))

	def test_a_long_step_name_still_runs_once(self):
		long_step = "Class " + "x" * 134
		workflow = make_workflow(
			"_Test Followup Long Step",
			[("Welcome", None, 1), (long_step, None, 1)],
			actions=[self.email_on(STEP_REACHED)],
		).name
		card = add_card(self.person, workflow)
		move(card, long_step)

		run_actions(card, STEP_REACHED, long_step)
		run_actions(card, STEP_REACHED, long_step)

		self.assertEqual(runs(card), ["Done"])
		self.assertEqual(self.sendmail.call_count, 1)

	def test_a_card_closed_by_a_merge_runs_no_card_closed_actions(self):
		workflow = self.workflow(self.email_on(CARD_CLOSED))
		kept = add_card(self.person, workflow)
		repeated = add_card(make_person("_Test Followup", "Duplicate").name, workflow)
		frappe.db.set_value(CARD, repeated, "person", self.person)

		self.assertEqual(queued_events(lambda: close_repeated_cards(self.person)), [])
		self.assertEqual(frappe.db.get_value(CARD, repeated, "status"), CLOSED)
		self.assertEqual(queued_events(lambda: move(kept, status=CLOSED)), [(CARD_CLOSED, "Welcome")])

	def test_deleting_a_card_deletes_its_runs(self):
		card = add_card(self.person, self.workflow(self.email_on(CARD_OPENED)))
		run_actions(card, CARD_OPENED, "Welcome")

		frappe.delete_doc(CARD, card)

		self.assertEqual(runs(card), [])

	def test_an_action_needs_its_fields_a_known_step_and_known_placeholders(self):
		refused = (
			{"run_on": CARD_OPENED},
			{"run_on": CARD_OPENED, "action": "Send Email", "purpose": CHURCH_NEWS},
			{"run_on": CARD_OPENED, "action": "Send Text", "message": "Hi"},
			{"run_on": CARD_OPENED, "action": "Add to Group"},
			{"run_on": CARD_OPENED, "action": "Add Tag"},
			{**self.email_on(STEP_REACHED, "Lunch")},
			{"run_on": CARD_OPENED, "action": "Send Text", "purpose": CHURCH_NEWS, "message": "{{ pastor }}"},
			{**self.email_on(CARD_OPENED), "email_template": self.unknown_template},
		)
		for index, action in enumerate(refused):
			with self.subTest(action=action), self.assertRaises(frappe.ValidationError):
				self.workflow(action, name=f"_Test Followup Refused {index}")

		text = {
			"run_on": CARD_OPENED,
			"action": "Send Text",
			"purpose": CHURCH_NEWS,
			"message": "At {{ step }}",
		}
		self.assertTrue(self.workflow(text))


class TestCardTriggers(RollbackEachTest):
	"""Step Reached and Card Closed: a card on one workflow starts a card on another."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.first = make_workflow("_Test Followup First", STEPS).name

	def setUp(self):
		super().setUp()
		self.enterContext(patch.object(frappe.db, "commit"))
		self.person = make_person("_Test Followup", "Trigger").name

	def workflow_on(self, name, trigger, step=None, value=None):
		rows = [{"trigger": trigger, "value": value or self.first, "step": step}]
		return make_workflow(name, STEPS, triggers=rows).name

	def cards_on(self, workflow):
		return frappe.get_all(CARD, filters={"person": self.person, "workflow": workflow}, pluck="name")

	def test_reaching_a_step_opens_one_card_on_the_workflow_waiting_for_it(self):
		at_class = self.workflow_on("_Test Followup At Class", STEP_REACHED, "Class")
		any_step = self.workflow_on("_Test Followup Any Step", STEP_REACHED)
		card = add_card(self.person, self.first)

		run_actions(card, STEP_REACHED, "Welcome")
		self.assertEqual(self.cards_on(at_class), [])
		self.assertEqual(len(self.cards_on(any_step)), 1)

		move(card, "Class")
		run_actions(card, STEP_REACHED, "Class")
		run_actions(card, STEP_REACHED, "Class")
		started = frappe.get_doc(CARD, self.cards_on(at_class)[0])
		self.assertEqual(len(self.cards_on(at_class)), 1)
		self.assertEqual((started.source_type, started.source_name), (CARD, card))
		self.assertEqual(started.reason, f"Step Reached: {self.first}")

	def test_a_card_queues_the_events_another_workflow_waits_for(self):
		self.workflow_on("_Test Followup Waiting", CARD_CLOSED)
		card = add_card(self.person, self.first)

		self.assertEqual(queued_events(lambda: move(card, "Class")), [])
		self.assertEqual(queued_events(lambda: move(card, status=CLOSED)), [(CARD_CLOSED, "Class")])

	def test_closing_a_card_opens_one_card_on_the_workflow_waiting_for_it(self):
		after = self.workflow_on("_Test Followup After", CARD_CLOSED)
		card = add_card(self.person, self.first)

		run_actions(card, STEP_REACHED, "Welcome")
		self.assertEqual(self.cards_on(after), [])

		move(card, status=CLOSED)
		run_actions(card, CARD_CLOSED, "Welcome")
		run_actions(card, CARD_CLOSED, "Welcome")
		self.assertEqual(len(self.cards_on(after)), 1)

	def test_a_trigger_row_with_a_step_starts_only_on_that_step(self):
		at_class = self.workflow_on("_Test Followup Only Class", STEP_REACHED, "Class")

		self.assertEqual(start_cards(STEP_REACHED, self.person, None, value=self.first, step="Done"), [])
		self.assertEqual(
			start_cards(STEP_REACHED, self.person, None, value=self.first, step="Class"),
			self.cards_on(at_class),
		)

	def test_a_closed_trigger_keeps_no_step(self):
		after = self.workflow_on("_Test Followup Closed Step", CARD_CLOSED, "Class")

		self.assertIsNone(frappe.get_doc("Follow-up Workflow", after).triggers[0].step)

	def test_a_workflow_must_name_another_workflow_and_one_of_its_steps(self):
		with self.assertRaises(frappe.ValidationError):
			self.workflow_on("_Test Followup Lunch", STEP_REACHED, "Lunch")
		with self.assertRaises(frappe.ValidationError):
			make_workflow("_Test Followup Blank", STEPS, triggers=[{"trigger": CARD_CLOSED}])

		workflow = frappe.get_doc("Follow-up Workflow", self.first)
		workflow.append("triggers", {"trigger": CARD_CLOSED, "value": self.first})
		with self.assertRaises(frappe.ValidationError):
			workflow.save()


class TestFollowupActionChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.workflow_b = make_workflow("_Test Followup Action B", STEPS, church=cls.branch_b).name
		cls.group_b = make_group("_Test Followup Action Group B", church=cls.branch_b)

	def setUp(self):
		super().setUp()
		self.enterContext(patch.object(frappe.db, "commit"))

	def test_a_workflow_cannot_name_another_churches_group_or_workflow(self):
		join = {"run_on": CARD_OPENED, "action": "Add to Group", "group": self.group_b}
		with self.assertRaises(frappe.PermissionError):
			make_workflow("_Test Followup Their Group", STEPS, church=self.branch_a, actions=[join])

		theirs = {"trigger": CARD_CLOSED, "value": self.workflow_b}
		with self.assertRaises(frappe.PermissionError):
			make_workflow("_Test Followup Their Workflow", STEPS, church=self.branch_a, triggers=[theirs])

	def test_a_step_reached_starts_the_waiting_workflow_of_the_cards_church(self):
		first = make_workflow("_Test Followup Church First", STEPS, church=self.branch_a).name
		rows = [{"trigger": STEP_REACHED, "value": first, "step": "Class"}]
		waiting = make_workflow("_Test Followup Church Next", STEPS, church=self.branch_a, triggers=rows).name
		person = make_person("_Test Followup", "Church Step", church=self.branch_b).name
		card = add_card(person, first)

		run_actions(card, STEP_REACHED, "Class")

		started = frappe.get_all(CARD, filters={"person": person, "workflow": waiting}, pluck="church")
		self.assertEqual(started, [self.branch_a])

	def test_a_church_reads_only_its_own_action_runs(self):
		tag = {
			"run_on": CARD_OPENED,
			"action": "Add Tag",
			"tag": ensure("Tag", {"name": "_Test Followup Scope"}),
		}
		workflow_a = make_workflow("_Test Followup Action A", STEPS, church=self.branch_a, actions=[tag]).name
		workflow_b = frappe.get_doc("Follow-up Workflow", self.workflow_b)
		workflow_b.append("actions", tag)
		workflow_b.save()
		manager = ensure_user(
			"_test_followup_action_manager@example.com", "Manager", roles=("Church Manager",)
		)
		make_person("_Test Followup", "Manager", church=self.branch_a, user=manager)
		person = make_person("_Test Followup", "Both", church=self.branch_a).name

		mine = add_card(person, workflow_a)
		theirs = add_card(person, self.workflow_b)
		run_actions(mine, CARD_OPENED, "Welcome")
		run_actions(theirs, CARD_OPENED, "Welcome")

		self.assertEqual(frappe.db.get_value(ACTION_RUN, {"card": theirs}, "church"), self.branch_b)
		assert_scoped(
			self,
			ACTION_RUN,
			manager,
			frappe.db.get_value(ACTION_RUN, {"card": mine}),
			frappe.db.get_value(ACTION_RUN, {"card": theirs}),
		)
