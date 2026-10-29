# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.api.v1 import create_doc, update_doc
from frappe.desk.doctype.kanban_board.kanban_board import update_order_for_single_card
from frappe.desk.form.load import getdoc
from frappe.desk.form.save import savedocs
from frappe.email.doctype.notification.notification import get_context
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from churchit.church_people.followup import (
	CARD,
	CLOSED,
	OPEN,
	add_card,
	close_repeated_cards,
	get_open_card,
	wake_snoozed_cards,
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
from churchit.tests.test_notification_templates import shipped_templates


def make_workflow(name, steps, **values):
	"""A workflow whose *steps* are (step, user, due_in_days) rows."""
	return frappe.get_doc(
		{
			"doctype": "Follow-up Workflow",
			"workflow_name": name,
			"steps": [{"step": step, "assign_to": user, "due_in_days": days} for step, user, days in steps],
			**values,
		}
	).insert(ignore_permissions=True)


def open_todos(card):
	return frappe.get_all(
		"ToDo",
		filters={"reference_type": CARD, "reference_name": card, "status": "Open"},
		fields=["allocated_to", "date"],
	)


class TestFollowupCard(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.caller = ensure_user("_test_followup_caller@example.com", "Caller", roles=("Church Follow-up",))
		cls.visitor = ensure_user(
			"_test_followup_visitor@example.com", "Visitor", roles=("Church Follow-up",)
		)
		cls.staff = ensure_user("_test_followup_staff@example.com", "Staff", roles=("Church Staff",))
		cls.editor = ensure_user(
			"_test_followup_editor@example.com", "Editor", roles=("Church Staff", "Church People Editor")
		)
		cls.workflow = make_workflow(
			"_Test Card Newcomers", [("Call", cls.caller, 2), ("Visit", cls.visitor, 7), ("Pray", None, 0)]
		).name

	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Card", "Newcomer")

	def test_add_card_returns_the_open_card_on_a_second_call(self):
		first = add_card(self.person.name, self.workflow, reason="Connection Card")

		self.assertEqual(add_card(self.person.name, self.workflow), first)
		self.assertEqual(frappe.db.count(CARD, {"person": self.person.name}), 1)

	def test_a_second_open_card_on_one_workflow_is_refused(self):
		add_card(self.person.name, self.workflow)

		with self.assertRaises(frappe.DuplicateEntryError):
			frappe.get_doc({"doctype": CARD, "person": self.person.name, "workflow": self.workflow}).insert()

	def test_a_step_the_workflow_does_not_have_is_refused(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		card.step = "Bake a Cake"

		with self.assertRaisesRegex(frappe.ValidationError, "not a step"):
			card.save()

	def test_a_new_card_starts_on_the_first_step_assigned_and_due(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))

		self.assertEqual((card.step, str(card.due_on)), ("Call", add_days(today(), 2)))
		self.assertEqual(open_todos(card.name), [{"allocated_to": self.caller, "date": card.due_on}])

	def test_moving_a_card_moves_its_due_date_and_assignment(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		card.step = "Visit"
		card.save()

		due_on = getdate(add_days(today(), 7))
		self.assertEqual(open_todos(card.name), [{"allocated_to": self.visitor, "date": due_on}])
		self.assertEqual(frappe.parse_json(frappe.db.get_value(CARD, card.name, "_assign")), [self.visitor])

	def test_a_step_without_a_user_leaves_no_one_assigned(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		card.step = "Pray"
		card.save()

		self.assertEqual(open_todos(card.name), [])

	def test_the_assignee_add_card_names_takes_the_card(self):
		card = add_card(self.person.name, self.workflow, assignee=self.visitor)

		self.assertEqual([todo.allocated_to for todo in open_todos(card)], [self.visitor])

	def test_dragging_a_card_on_its_board_moves_its_step_and_assignment(self):
		card = add_card(self.person.name, self.workflow)
		board = frappe.db.get_value("Follow-up Workflow", self.workflow, "kanban_board")

		frappe.set_user(self.caller)
		update_order_for_single_card(board, card, "Call", "Visit", 0, 0)

		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(CARD, card, "step"), "Visit")
		self.assertEqual([todo.allocated_to for todo in open_todos(card)], [self.visitor])

	def test_closing_a_card_closes_its_to_dos_and_reopening_assigns_it_again(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		card.status = CLOSED
		card.save()

		self.assertEqual(str(card.closed_on), today())
		self.assertEqual(open_todos(card.name), [])

		card.status = "Open"
		card.save()
		self.assertIsNone(card.closed_on)
		self.assertEqual([todo.allocated_to for todo in open_todos(card.name)], [self.caller])

	def test_the_assignee_is_sent_one_email(self):
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Follow-up Outgoing",
				"email_id": "_test_followup_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		sent_before = frappe.db.count("Email Queue Recipient", {"recipient": self.caller})
		frappe.set_user(self.editor)
		add_card(self.person.name, self.workflow)
		frappe.set_user("Administrator")

		self.assertEqual(
			frappe.db.count("Email Queue Recipient", {"recipient": self.caller}), sent_before + 1
		)

	def test_a_snoozed_card_wakes_on_its_date(self):
		woken = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		woken.db_set("snoozed_until", today())
		sleeping = frappe.get_doc(CARD, add_card(make_person("_Test Card", "Sleeper").name, self.workflow))
		sleeping.db_set("snoozed_until", add_days(today(), 1))

		wake_snoozed_cards()

		self.assertIsNone(frappe.db.get_value(CARD, woken.name, "snoozed_until"))
		self.assertEqual(str(frappe.db.get_value(CARD, sleeping.name, "snoozed_until")), add_days(today(), 1))

	def test_the_follow_up_role_reaches_only_the_cards_assigned_to_it(self):
		mine = add_card(self.person.name, self.workflow)
		theirs = add_card(make_person("_Test Card", "Theirs").name, self.workflow, assignee=self.visitor)

		frappe.set_user(self.caller)
		listed = frappe.get_list(CARD, pluck="name")
		self.assertIn(mine, listed)
		self.assertNotIn(theirs, listed)
		self.assertTrue(frappe.has_permission(CARD, "write", doc=mine))
		self.assertFalse(frappe.has_permission(CARD, "read", doc=theirs))
		with self.assertRaises(frappe.PermissionError):
			getdoc(CARD, theirs)

		frappe.set_user(self.staff)
		self.assertTrue({mine, theirs} <= set(frappe.get_list(CARD, pluck="name")))

	def test_the_follow_up_role_saves_its_card_from_the_form_but_cannot_claim_another(self):
		mine = frappe.get_doc(CARD, add_card(self.person.name, self.workflow)).as_dict()
		theirs = frappe.get_doc(
			CARD, add_card(make_person("_Test Card", "Other").name, self.workflow, assignee=self.visitor)
		)

		frappe.set_user(self.caller)
		# Like as_dict, the form sends the card without its assignees.
		savedocs(frappe.as_json({**mine, "snoozed_until": add_days(today(), 3)}), "Save")
		theirs._assign = frappe.as_json([self.caller])
		theirs.outcome = "_Test claimed"
		with self.assertRaises(frappe.PermissionError):
			theirs.save()

		frappe.set_user("Administrator")
		self.assertEqual(str(frappe.db.get_value(CARD, mine.name, "snoozed_until")), add_days(today(), 3))

	def test_the_card_form_shows_the_persons_contact_details(self):
		self.person.append("phones", {"phone_number": "555 0100", "is_primary": 1})
		self.person.append("emails", {"email_address": "_test_card_newcomer@example.com", "is_primary": 1})
		self.person.save()
		card = add_card(self.person.name, self.workflow)

		frappe.set_user(self.caller)
		getdoc(CARD, card)

		contact = frappe.response.docs[-1].get("__onload")["contact"]
		self.assertEqual(contact, {"phone": "555 0100", "email": "_test_card_newcomer@example.com"})

	def test_after_a_merge_only_the_oldest_open_card_on_a_workflow_stays_open(self):
		other = make_workflow("_Test Card Other", [("Call", self.caller, 1)]).name
		kept = add_card(self.person.name, self.workflow)
		repeated = add_card(make_person("_Test Card", "Duplicate").name, self.workflow)
		elsewhere = add_card(self.person.name, other)
		# A merge repoints the Link in SQL, as Frappe's rename does.
		frappe.db.set_value(CARD, repeated, "person", self.person.name)

		self.assertEqual(close_repeated_cards(self.person.name), [repeated])
		self.assertEqual(frappe.db.get_value(CARD, kept, "status"), "Open")
		self.assertEqual(frappe.db.get_value(CARD, elsewhere, "status"), "Open")
		self.assertEqual(open_todos(repeated), [])

	def test_the_overdue_notice_names_the_card_and_reaches_its_assignee(self):
		card = frappe.get_doc(CARD, add_card(self.person.name, self.workflow))
		notification, markdown = shipped_templates("church_communications", "Follow-up Card Overdue")
		context = get_context(card)

		for template in (notification["subject"], notification["message"], markdown):
			self.assertIn("_Test Card Newcomer", frappe.render_template(template, context))
		self.assertIn("Call", frappe.render_template(markdown, context))
		self.assertEqual(markdown, notification["message"])
		self.assertTrue(frappe.safe_eval(notification["condition"], None, context))
		recipients, _cc, _bcc = frappe.get_doc(notification).get_list_of_recipients(card, context)
		self.assertIn(self.caller, recipients)

	def test_the_overdue_notice_picks_open_cards_due_yesterday_that_are_awake(self):
		cards = {}
		for key in ("overdue", "snoozed", "closed"):
			card = frappe.get_doc(CARD, add_card(make_person("_Test Card", key.title()).name, self.workflow))
			card.db_set(
				{"due_on": add_days(today(), -1), "snoozed_until": today() if key == "snoozed" else None}
			)
			cards[key] = card.name
		frappe.db.set_value(CARD, cards["closed"], "status", CLOSED)

		due = [
			doc.name
			for doc in frappe.get_doc("Notification", "Follow-up Card Overdue").get_documents_for_today()
		]

		self.assertIn(cards["overdue"], due)
		self.assertNotIn(cards["snoozed"], due)
		self.assertNotIn(cards["closed"], due)


class TestFollowupCardChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = cls.make_user("manager_a", cls.branch_a)
		cls.workflow_a = make_workflow("_Test Card Branch A", [("Call", None, 1)], church=cls.branch_a).name
		cls.workflow_b = make_workflow("_Test Card Branch B", [("Call", None, 1)], church=cls.branch_b).name

	@classmethod
	def make_user(cls, key, church):
		user = ensure_user(f"_test_followup_{key}@example.com", key, roles=("Church Manager",))
		make_person(key, "_Test Card", church=church, user=user)
		return user

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def rest(self, call, *args, **data):
		"""Call a REST handler of `frappe.api.v1` with *data* as the request body."""
		frappe.local.form_dict = frappe._dict(data=json.dumps(data))
		return call(*args)

	def test_a_card_belongs_to_its_workflows_church(self):
		person = make_person("_Test Card", "Anyone", church=self.branch_a).name
		in_a = add_card(person, self.workflow_a)
		in_b = add_card(person, self.workflow_b)

		self.assertEqual(frappe.db.get_value(CARD, in_b, "church"), self.branch_b)
		assert_scoped(self, CARD, self.manager_a, in_a, in_b)

	def test_a_card_for_another_churches_person_is_refused(self):
		person_a = make_person("_Test Card", "Mine", church=self.branch_a).name
		person_b = make_person("_Test Card", "Theirs", church=self.branch_b).name
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": CARD, "person": person_b, "workflow": self.workflow_a}).insert()
		mine = (
			frappe.get_doc({"doctype": CARD, "person": person_a, "workflow": self.workflow_a}).insert().name
		)

		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, CARD, mine, person=person_b)
		self.assertEqual(frappe.db.get_value(CARD, mine, "person"), person_a)

	def test_a_job_still_opens_a_card_for_another_churches_person(self):
		person_b = make_person("_Test Card", "Visiting", church=self.branch_b).name
		frappe.set_user(self.manager_a)

		card = add_card(person_b, self.workflow_a)

		self.assertEqual(frappe.db.get_value(CARD, card, "person"), person_b)

	def test_a_card_on_another_churches_workflow_is_refused(self):
		"""The card takes the workflow's church after Frappe checked the create right on the card as sent."""
		person = make_person("_Test Card", "Own", church=self.branch_a).name
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.PermissionError):
			self.rest(create_doc, CARD, person=person, workflow=self.workflow_b)
		mine = self.rest(create_doc, CARD, person=person, workflow=self.workflow_a).name
		with self.assertRaises(frappe.PermissionError):
			self.rest(update_doc, CARD, mine, workflow=self.workflow_b)

		self.assertEqual(
			frappe.get_all(CARD, filters={"person": person}, pluck="workflow"), [self.workflow_a]
		)

	def test_a_job_still_opens_a_card_on_another_churches_workflow(self):
		person = make_person("_Test Card", "Checked In", church=self.branch_a).name
		frappe.set_user(self.manager_a)

		card = add_card(person, self.workflow_b)

		self.assertEqual(frappe.db.get_value(CARD, card, "church"), self.branch_b)


class TestOpenCardLookup(FrappeTestCase):
	"""Two jobs opening a card for one person, each on its own connection."""

	PERSON = "_Test Card Race"
	CARD_NAME = "_Test Card Race Card"
	WORKFLOW = "_Test Card Race Workflow"

	def setUp(self):
		# Plain rows, committed so the other connection sees them, and no hooks to queue jobs.
		frappe.get_doc(
			{"doctype": "Person", "name": self.PERSON, "first_name": "_Test Card", "last_name": "Race"}
		).db_insert()
		frappe.db.commit()
		self.addCleanup(self.delete_rows)

	def delete_rows(self):
		frappe.db.delete(CARD, {"name": self.CARD_NAME})
		frappe.db.delete("Person", {"name": self.PERSON})
		frappe.db.commit()

	def test_a_job_finds_the_card_another_job_committed_after_its_first_read(self):
		"""The interleaving that made duplicates: one job reads, the other commits a card, then the first
		locks the Person and looks for an open card."""
		with self.secondary_connection():
			frappe.db.get_value("Person", self.PERSON)

		with self.primary_connection():
			frappe.get_doc(
				{
					"doctype": CARD,
					"name": self.CARD_NAME,
					"person": self.PERSON,
					"workflow": self.WORKFLOW,
					"status": OPEN,
				}
			).db_insert()
			frappe.db.commit()

		with self.secondary_connection():
			# A plain read still answers from the snapshot of the first read, as add_card's lookup did.
			self.assertIsNone(frappe.db.get_value(CARD, self.CARD_NAME))
			self.assertEqual(get_open_card(self.PERSON, self.WORKFLOW), self.CARD_NAME)
