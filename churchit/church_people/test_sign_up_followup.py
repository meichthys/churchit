# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Signed Up trigger (REG12): a Confirmed sign-up starts a card for each new attendee Person."""

from unittest.mock import patch

import frappe

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CONFIRMED,
	PENDING,
	link_registrant,
)
from churchit.church_people.followup import SIGNED_UP, start_sign_up_cards
from churchit.church_people.test_followup import cards_of, workflow_on
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)

SIGN_UP = "Function Sign-Up"
CAMP = "_Test Youth Camp"


def queued_people(save):
	"""Run *save*, then the card job it queued, and return the people the job was given."""
	with patch("frappe.enqueue") as enqueue:
		save()
	[job] = [
		call.kwargs for call in enqueue.call_args_list if call.args and call.args[0] is start_sign_up_cards
	] or [None]
	if not job:
		return []
	start_sign_up_cards(**{key: job[key] for key in ("sign_up", "people")})
	return job["people"]


def make_camp(**values):
	return make_function(
		"_Test Followup Camp", type=ensure("Function Type", {"type": CAMP}), allow_sign_ups=1, **values
	).name


class TestSignUpFollowup(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure("Function Type", {"type": CAMP})
		cls.other_type = ensure("Function Type", {"type": "_Test Followup Other"})

	def setUp(self):
		super().setUp()
		self.camp_workflow = workflow_on("_Test Signed Up Camp", (SIGNED_UP, CAMP))
		workflow_on("_Test Signed Up Other", (SIGNED_UP, self.other_type))
		self.function = make_camp()
		self.registrant, self.child, self.friend = (
			make_person(name, "_Test Signed Up").name for name in ("Rae", "Kit", "Flo")
		)

	def sign_up(self, *attendees):
		"""An items-only sign-up by the registrant for *attendees*: Person names, or a typed row."""
		rows = [row if isinstance(row, dict) else {"person": row} for row in attendees]
		doc = frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": self.function,
				"person": self.registrant,
				"attending": 0,
				"attendees": rows,
			}
		)
		return doc, queued_people(doc.insert)

	def test_a_confirmed_sign_up_opens_one_card_per_attendee_person(self):
		doc, people = self.sign_up(self.child, self.friend, {"attendee_name": "_Test Typed Guest"})

		self.assertEqual(doc.status, CONFIRMED)
		self.assertEqual(people, sorted([self.child, self.friend]))
		for person in (self.child, self.friend):
			self.assertEqual(cards_of(person), [self.camp_workflow])
		card = frappe.get_doc("Follow-up Card", {"person": self.child})
		self.assertEqual((card.source_type, card.source_name), (SIGN_UP, doc.name))
		self.assertEqual(card.reason, f"Signed Up: {CAMP}")

	def test_confirming_again_opens_no_second_card(self):
		doc, _people = self.sign_up(self.child)

		self.assertEqual(queued_people(doc.save), [])

		frappe.db.set_value(SIGN_UP, doc.name, "status", PENDING)
		doc.reload()
		doc.status = CONFIRMED
		doc.flags.set_by_code = True
		self.assertEqual(queued_people(doc.save), [self.child])
		self.assertEqual(frappe.db.count("Follow-up Card", {"person": self.child}), 1)

	def test_a_sign_up_that_is_not_confirmed_opens_no_card(self):
		doc, _people = self.sign_up(self.child)
		frappe.db.delete("Follow-up Card", {"person": self.child})
		frappe.db.set_value(SIGN_UP, doc.name, "status", PENDING)
		doc.reload()
		doc.notes = "_Test waiting for approval"

		self.assertEqual(queued_people(doc.save), [])
		self.assertEqual(cards_of(self.child), [])

	def test_a_new_attendee_person_opens_a_card_for_that_person_only(self):
		doc, _people = self.sign_up(self.child)
		doc.append("attendees", {"person": self.friend})

		self.assertEqual(queued_people(doc.save), [self.friend])
		self.assertEqual(cards_of(self.friend), [self.camp_workflow])

	def test_a_guest_sign_up_opens_the_card_after_its_person_is_linked(self):
		function = make_camp(publish=1, allow_guest_sign_ups=1)
		frappe.set_user("Guest")
		doc = frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": function,
				"registrant_name": "Rae _Test Signed Up",
				"email": "_test_signed_up_guest@example.com",
				"attending": 1,
			}
		)
		doc.flags.ignore_permissions = True
		self.assertEqual(queued_people(doc.insert), [])

		people = queued_people(lambda: link_registrant(doc.name))
		frappe.set_user("Administrator")

		person = frappe.db.get_value(SIGN_UP, doc.name, "person")
		self.assertTrue(person)
		self.assertEqual(people, [person])
		self.assertEqual(cards_of(person), [self.camp_workflow])


class TestSignUpFollowupChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()

	def setUp(self):
		super().setUp()
		self.in_a = workflow_on("_Test Signed Up A", (SIGNED_UP, None), church=self.branch_a)
		self.in_b = workflow_on("_Test Signed Up B", (SIGNED_UP, None), church=self.branch_b)
		self.person = make_person("_Test Signed Up", "Visitor", church=self.branch_b).name

	def sign_up(self, function):
		doc = frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": function,
				"person": self.person,
				"attendees": [{"person": self.person}],
			}
		)
		queued_people(doc.insert)

	def test_a_sign_up_starts_the_workflows_of_the_church_holding_the_function(self):
		self.sign_up(make_camp(church=self.branch_a))

		self.assertEqual(cards_of(self.person), [self.in_a])

	def test_a_sign_up_for_a_shared_function_starts_the_persons_own_churchs_workflows(self):
		self.sign_up(make_camp(church=self.branch_a, is_shared=1))

		self.assertEqual(cards_of(self.person), [self.in_b])
