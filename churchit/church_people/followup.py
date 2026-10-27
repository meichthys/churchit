# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Follow-up cards: one person on one workflow, moved through its steps until someone closes it.

`add_card` is the one way code opens a card, and `start_cards` is the one way an event about one
person (a connection card, a first check-in, a life event, a membership change) reaches the
workflows that start on it. The daily `start_smart_list_cards` reads the smart-list triggers
itself. A workflow's actions (an email, a text, a group, a tag) run in `run_actions` when a card
opens, reaches a step or closes, and the last two also start the workflows waiting for them.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.permissions import get_doctype_roles
from frappe.utils import sha256_hash, today

from churchit.church_ministries.doctype.function_check_in.function_check_in import VOLUNTEER
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import CONFIRMED
from churchit.church_people import smart_lists
from churchit.church_scope import church_filters

CARD = "Follow-up Card"
WORKFLOW = "Follow-up Workflow"
STEP = "Follow-up Step"
TRIGGER = "Follow-up Trigger"
ACTION = "Follow-up Action"
ACTION_RUN = "Follow-up Action Run"
OPEN = "Open"
CLOSED = "Closed"
FOLLOW_UP_ROLE = "Church Follow-up"

CONNECTION_CARD = "Connection Card"
FIRST_CHECK_IN = "First Check-In"
LIFE_EVENT_ADDED = "Life Event Added"
MEMBERSHIP_TYPE_BECOMES = "Membership Type Becomes"
MEMBER_STATUS_BECOMES = "Member Status Becomes"
ON_SMART_LIST = "On Smart List"
SIGNED_UP = "Signed Up"
FORM_SUBMITTED = "Form Submitted"
# What happens to a card. The last two are also triggers that start another workflow.
CARD_OPENED = "Card Opened"
STEP_REACHED = "Step Reached"
CARD_CLOSED = "Card Closed"
CARD_TRIGGERS = (STEP_REACHED, CARD_CLOSED)
# What a trigger row's "Which" value names. follow_up_workflow.js offers the same pickers.
VALUE_TYPES = {
	CONNECTION_CARD: "Connection Card Interest",
	FIRST_CHECK_IN: "Function Type",
	LIFE_EVENT_ADDED: "Life Event Type",
	MEMBERSHIP_TYPE_BECOMES: "Membership Type",
	MEMBER_STATUS_BECOMES: "Member Status",
	ON_SMART_LIST: "Report",
	SIGNED_UP: "Function Type",
	FORM_SUBMITTED: "Question Set",
	STEP_REACHED: WORKFLOW,
	CARD_CLOSED: WORKFLOW,
}
# A Follow-up Action Run's status.
DONE = "Done"
SKIPPED = "Skipped"
FAILED = "Failed"
# The trigger each membership field starts, by the field a membership_changed event names.
MEMBERSHIP_TRIGGERS = {"membership": MEMBERSHIP_TYPE_BECOMES, "membership_status": MEMBER_STATUS_BECOMES}


def add_card(
	person: str,
	workflow: str,
	reason: str | None = None,
	assignee: str | None = None,
	source=None,
) -> str:
	"""Open a card for *person* on *workflow* and return its name, or the name of the card already open.

	*assignee* (a User) takes the card instead of its step's user, and *source* is the
	document that started it. A person has at most one open card per workflow, so calling
	this twice for the same reason opens one card.
	"""
	existing = get_open_card(person, workflow)
	if existing:
		return existing

	card = frappe.get_doc(
		{
			"doctype": CARD,
			"person": person,
			"workflow": workflow,
			"reason": reason,
			"source_type": source.doctype if source else None,
			"source_name": source.name if source else None,
		}
	)
	card.flags.assignee = assignee
	card.insert(ignore_permissions=True)
	return card.name


def get_open_card(person: str, workflow: str, exclude: str = "") -> str | None:
	"""The open card of *person* on *workflow* other than *exclude*, read after locking the Person row.

	Two jobs for one person (a connection card and a check-in) wait on that lock instead of both
	inserting. The card is read with a lock too: a plain read returns the snapshot the job took at its
	first read, which is older than the lock and misses the card the other job has just committed.
	"""
	frappe.db.get_value("Person", person, "name", for_update=True)
	# church-scope: one person's cards on one workflow, which belongs to one church
	return frappe.db.get_value(
		CARD,
		{"person": person, "workflow": workflow, "status": OPEN, "name": ("!=", exclude)},
		for_update=True,
	)


def start_cards(
	trigger: str,
	person: str,
	church: str | None,
	value: str | None = None,
	source=None,
	*,
	step: str | None = None,
) -> list[str]:
	"""Open a card for *person* on each active workflow of *church* that starts on *trigger*.

	A trigger row with no value starts on every *value*; one with a value starts only on that one.
	A row with a step starts only on that *step*.
	"""
	workflows = frappe.get_all(WORKFLOW, filters=church_filters(church, is_active=1), pluck="name")
	if not workflows:
		return []
	rows = frappe.get_all(
		TRIGGER,
		filters={"parenttype": WORKFLOW, "parent": ("in", workflows), "trigger": trigger},
		fields=["parent", "value", "step"],
	)
	starting = sorted(
		{
			row.parent
			for row in rows
			if (not row.value or row.value == value) and (not row.step or row.step == step)
		}
	)
	reason = describe_trigger(trigger, value)
	return [add_card(person, workflow, reason=reason, source=source) for workflow in starting]


def start_person_cards(trigger: str, person: str, value: str | None) -> list[str]:
	"""start_cards on the workflows of *person*'s own church."""
	return start_cards(trigger, person, frappe.db.get_value("Person", person, "church"), value=value)


def describe_trigger(trigger: str, value: str | None) -> str:
	"""The reason a card started, as its form shows it."""
	return _("{0}: {1}").format(_(trigger), value) if value else _(trigger)


def first_step(workflow: str) -> str | None:
	return frappe.db.get_value(STEP, {"parenttype": WORKFLOW, "parent": workflow}, "step", order_by="idx asc")


def has_card_permission(doc, ptype=None, user=None) -> bool:
	"""has_permission hook for Follow-up Card: the follow-up role reaches only the cards assigned to it.

	Frappe reads any falsy return as a refusal, so every other user gets True.
	"""
	user = user or frappe.session.user
	if not is_follow_up_only(user):
		return True
	if doc.is_new():
		return False
	# The stored assignees: a form sends none, and a caller could send any.
	return user in json.loads(frappe.db.get_value(CARD, doc.name, "_assign") or "[]")


def card_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions for Follow-up Card: the follow-up role lists only the cards assigned to it."""
	user = user or frappe.session.user
	if not is_follow_up_only(user):
		return ""
	# Frappe keeps the assignees in `_assign` as a JSON list; a quoted name cannot match a longer one.
	quoted = json.dumps(user).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
	return f"`tabFollow-up Card`.`_assign` like {frappe.db.escape(f'%{quoted}%')}"


def is_follow_up_only(user: str) -> bool:
	"""True when *user* holds rights on Follow-up Cards only through the Church Follow-up role."""
	return set(get_doctype_roles(CARD)) & set(frappe.get_roles(user)) == {FOLLOW_UP_ROLE}


def on_membership_changed(
	person: str, field: str, old: str | None = None, new: str | None = None
) -> list[str]:
	"""churchit_people_events handler: a new membership type or status starts the workflows waiting for it."""
	trigger = MEMBERSHIP_TRIGGERS.get(field)
	if not (trigger and new):
		return []
	return start_person_cards(trigger, person, new)


def on_life_event_added(person: str, event_type: str | None = None, date=None) -> list[str]:
	"""churchit_people_events handler: a new life event starts the workflows waiting for its type."""
	return start_person_cards(LIFE_EVENT_ADDED, person, event_type)


def on_check_in(doc, method=None) -> None:
	"""after_insert on Function Check-In: a person's first check-in ever starts the First Check-In workflows.

	The cards start after the check-in commits, so a follow-up problem never stops the Check-In Station.
	A volunteer who serves is not a newcomer, so a Volunteer check-in neither starts a card nor counts.
	"""
	if doc.check_in_kind == VOLUNTEER:
		return
	# church-scope: a first check-in is the first at any church
	if frappe.db.exists(
		"Function Check-In",
		{"person": doc.person, "name": ("!=", doc.name), "check_in_kind": ("!=", VOLUNTEER)},
	):
		return
	frappe.enqueue(start_check_in_cards, enqueue_after_commit=True, check_in=doc.name)


def start_check_in_cards(check_in: str) -> list[str]:
	"""Background job: start the First Check-In workflows of the church that held the function.

	A function shared with every church belongs to none of them, so the person's own church follows them up.
	"""
	doc = frappe.get_doc("Function Check-In", check_in)
	church = doc.church or frappe.db.get_value("Person", doc.person, "church")
	return start_cards(FIRST_CHECK_IN, doc.person, church, value=doc.function_type, source=doc)


def on_sign_up(doc, method=None) -> None:
	"""on_update on Function Sign-Up: a Confirmed sign-up starts the Signed Up workflows of each new attendee.

	Every attendee Person is new when the sign-up has just become Confirmed. The cards start after the
	commit, so a follow-up problem never stops a sign-up, and the job runs as the user who saved it,
	a guest included.
	"""
	if doc.status != CONFIRMED:
		return
	people = doc.get_attendee_people()
	before = doc.get_doc_before_save()
	if before and before.status == CONFIRMED:
		people -= before.get_attendee_people()
	if people:
		frappe.enqueue(
			start_sign_up_cards, enqueue_after_commit=True, sign_up=doc.name, people=sorted(people)
		)


def start_sign_up_cards(sign_up: str, people: list[str]) -> list[str]:
	"""Background job: start the Signed Up workflows of each of *people*, attendees of one sign-up.

	A sign-up of a function shared with every church belongs to none of them, so each person's own
	church follows them up.
	"""
	doc = frappe.get_doc("Function Sign-Up", sign_up)
	function_type = frappe.db.get_value("Function", doc.function, "type")
	cards = []
	for person in people:
		church = doc.church or frappe.db.get_value("Person", person, "church")
		cards += start_cards(SIGNED_UP, person, church, value=function_type, source=doc)
	return cards


def queue_actions(card: Document, event: str) -> None:
	"""Run the actions of *card*'s workflow for *event* in a job after the commit, when there is anything to do."""
	if has_actions(card.workflow, event):
		# Not `event=`: frappe.enqueue takes that argument for itself.
		frappe.enqueue(run_actions, enqueue_after_commit=True, card=card.name, run_on=event, step=card.step)


def has_actions(workflow: str, event: str) -> bool:
	"""True when *workflow* has an action for *event*, or another workflow starts on it."""
	# church-scope: the rows of one workflow, and the triggers naming it, which its church alone may add
	if frappe.db.exists(ACTION, {"parenttype": WORKFLOW, "parent": workflow, "run_on": event}):
		return True
	return event in CARD_TRIGGERS and bool(
		frappe.db.exists(TRIGGER, {"parenttype": WORKFLOW, "trigger": event, "value": workflow})
	)


def run_actions(card: str, run_on: str, step: str) -> None:
	"""Background job: run the actions of *card*'s workflow for *run_on* (an event) at *step*, then start the
	workflows waiting for it.

	It runs as the user who saved the card, Guest after a connection card, so it writes with
	ignore_permissions. An action with no step runs at every step.
	"""
	doc = frappe.get_doc(CARD, card)
	for row in frappe.get_doc(WORKFLOW, doc.workflow).actions:
		if row.run_on == run_on and not (run_on == STEP_REACHED and row.step and row.step != step):
			run_action(doc, row, run_on, step)
	if run_on in CARD_TRIGGERS:
		start_cards(run_on, doc.person, doc.church, value=doc.workflow, step=step, source=doc)


def run_action(card: Document, row: Document, event: str, step: str) -> None:
	"""Run one action once for *event* at *step*, and log it. A failed action is logged and never retried.

	The log is inserted first: its unique key stops a second job, which waits for this one to commit.
	Each action is committed, because a text leaves at once and a later error must not forget it.
	"""
	# A step name alone can fill the Data field, so the keys hold a short hash of it.
	key = f"{row.name}:{event}:{sha256_hash(step)[:10]}"
	run = frappe.get_doc(
		{
			"doctype": ACTION_RUN,
			"key": f"{card.name}:{key}",
			"card": card.name,
			"workflow": card.workflow,
			"church": card.church,
			"event": event,
			"step": step,
			"action": row.action,
			"status": DONE,
		}
	)
	try:
		run.insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		return

	frappe.db.savepoint("follow_up_action")
	try:
		if not row.run(card, key, step):
			run.db_set("status", SKIPPED)
	except Exception as error:
		frappe.db.rollback(save_point="follow_up_action")
		run.db_set({"status": FAILED, "error": str(error)})
		frappe.log_error(
			f"Follow-up action {row.action} failed", reference_doctype=CARD, reference_name=card.name
		)
	frappe.db.commit()


def wake_snoozed_cards() -> None:
	"""Daily job: clear the snooze of every card whose date has come, so it is back on its board."""
	# church-scope: each card wakes on its own date; nothing here is shown to a user
	for name in frappe.get_all(CARD, filters={"snoozed_until": ("<=", today())}, pluck="name"):
		card = frappe.get_doc(CARD, name)
		card.snoozed_until = None
		card.save(ignore_permissions=True)


def start_smart_list_cards() -> None:
	"""Daily job: open a card for each person new to the smart list of an On Smart List trigger."""
	# church-scope: every church's workflows; each list is read inside its own workflow's church
	workflows = frappe.get_all(WORKFLOW, filters={"is_active": 1}, pluck="name")
	rows = frappe.get_all(
		TRIGGER,
		filters={"parenttype": WORKFLOW, "parent": ("in", workflows), "trigger": ON_SMART_LIST},
		fields=["parent", "value"],
	)
	for row in rows:
		add_smart_list_people(row.parent, row.value)


def add_smart_list_people(workflow: str, report: str) -> list[str]:
	"""Open a card on *workflow* for each living person of its church on the saved list *report*.

	A person the list added once is never added again, even after their card is closed and they
	drop off the list and come back.
	"""
	people = smart_lists.get_people(report, frappe.db.get_value(WORKFLOW, workflow, "church"))
	# church-scope: the cards of one workflow, which belongs to one church
	added_before = set(
		frappe.get_all(
			CARD,
			filters={"workflow": workflow, "source_type": "Report", "source_name": report},
			pluck="person",
		)
	)
	reason = describe_trigger(ON_SMART_LIST, report)
	source = frappe.get_doc("Report", report)
	return [
		add_card(person, workflow, reason=reason, source=source)
		for person in people
		if person not in added_before
	]


def close_repeated_cards(person: str) -> list[str]:
	"""Close every open card of *person* but the oldest on each workflow, and return the closed ones.

	Merging two people can leave the one kept with two open cards on one workflow. A card closed here
	runs no Card Closed actions or triggers, because the card kept carries on.
	"""
	# church-scope: one person's cards, each closed on its own workflow
	cards = frappe.get_all(
		CARD, filters={"person": person, "status": OPEN}, fields=["name", "workflow"], order_by="creation asc"
	)
	kept = {}
	closed = []
	for card in cards:
		if card.workflow not in kept:
			kept[card.workflow] = card.name
			continue
		close_quietly(
			card.name, _("Closed when two people were merged. {0} carries on.").format(kept[card.workflow])
		)
		closed.append(card.name)
	return closed


def close_quietly(card: str, outcome: str) -> None:
	"""Close *card* with *outcome* and run no Card Closed actions or triggers, for a merged or anonymized person."""
	doc = frappe.get_doc(CARD, card)
	doc.status = CLOSED
	doc.outcome = outcome
	doc.flags.closed_quietly = True
	doc.save(ignore_permissions=True)
