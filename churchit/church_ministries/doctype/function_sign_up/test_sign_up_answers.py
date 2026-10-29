# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import patch

import frappe

from churchit.church_people.privacy import anonymize
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.www.register import get_answer_rows, get_questions, sign_up

SIGN_UP = "Function Sign-Up"
QUESTIONS = [
	{"label": "Diet", "question_type": "Data", "is_required": 1},
	{"label": "Shirt size", "question_type": "Select", "options": "Small\nLarge"},
]


def make_question_set(title, **values):
	return frappe.get_doc(
		{"doctype": "Question Set", "title": title, "questions": QUESTIONS, **values}
	).insert(ignore_permissions=True)


def answer_rows(attendee, **answers):
	return [
		{"attendee": attendee, "question": question, "answer": answer} for question, answer in answers.items()
	]


class AnswersTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		frappe.db.set_value("Church", cls.church, "publish", 1)
		cls.question_set = make_question_set("_Test Camp Sign-Up Questions").name
		cls.function = make_function(
			"_Test Answered Camp",
			start_date="2031-06-01",
			allow_sign_ups=1,
			publish=1,
			allow_guest_sign_ups=1,
			question_set=cls.question_set,
		).name

	def setUp(self):
		super().setUp()
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def sign_up(self, answers=(), attendees=(), **values):
		return frappe.get_doc(
			{
				"doctype": SIGN_UP,
				"function": self.function,
				"registrant_name": "_Test Ana Answer",
				"email": "_test_ana_answer@example.com",
				"attendees": list(attendees),
				"answers": list(answers),
				**values,
			}
		).insert(ignore_permissions=True, set_child_names=False)  # keep the attendee names, as /register does

	def get_answers(self, sign_up):
		return {
			(row.attendee, row.question): (row.label, row.answer)
			for row in frappe.get_doc(SIGN_UP, sign_up).answers
		}

	def get_answer_rows(self, sign_up):
		return frappe.get_all(
			"Question Answer",
			filters={"parenttype": SIGN_UP, "parent": sign_up},
			fields=["name", "attendee", "question", "label", "answer"],
			order_by="idx",
		)


class TestAttendeeAnswers(AnswersTestCase):
	def test_a_required_question_left_blank_refuses_the_save(self):
		with self.assertRaises(frappe.MandatoryError):
			self.sign_up(answer_rows("", shirt_size="Small"))
		# An attendee with no answers at all leaves the required question blank too.
		with self.assertRaises(frappe.MandatoryError):
			self.sign_up(answer_rows("", diet="None"), [{"name": "kid-row-01", "attendee_name": "_Test Kid"}])

	def test_each_attendee_keeps_their_own_answers(self):
		sign_up = self.sign_up(
			answer_rows("", diet="None") + answer_rows("kid-row-02", diet="Vegan", shirt_size="Large"),
			[{"name": "kid-row-02", "attendee_name": "_Test Kid"}],
		)

		registrant = next(row.name for row in sign_up.attendees if row.attendee_name == "_Test Ana Answer")
		self.assertEqual(
			self.get_answers(sign_up.name),
			{
				(registrant, "diet"): ("Diet", "None"),
				("kid-row-02", "diet"): ("Diet", "Vegan"),
				("kid-row-02", "shirt_size"): ("Shirt size", "Large"),
			},
		)

	def test_an_answer_that_names_no_attendee_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(answer_rows("", diet="None") + answer_rows("not-a-row", diet="Vegan"))
		# With Attending unticked the registrant takes no seat, so no answer can be theirs.
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(answer_rows("", diet="None"), attending=0)

	def test_an_answer_that_does_not_fit_the_set_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(answer_rows("", diet="None", favourite_colour="Red"))
		with self.assertRaises(frappe.ValidationError):
			self.sign_up(answer_rows("", diet="None", shirt_size="Huge"))

	def test_a_saved_sign_up_is_checked_again_only_where_it_changed(self):
		sign_up = self.sign_up(answer_rows("", diet="None"))
		question_set = frappe.get_doc("Question Set", self.question_set)
		question_set.append("questions", {"label": "Allergies", "question_type": "Data", "is_required": 1})
		question_set.save(ignore_permissions=True)

		sign_up.reload()
		sign_up.notes = "_Test arrives late"
		sign_up.save(ignore_permissions=True)
		self.assertEqual(len(self.get_answers(sign_up.name)), 1)

		sign_up.append("attendees", {"attendee_name": "_Test Late Kid"})
		with self.assertRaises(frappe.MandatoryError):
			sign_up.save(ignore_permissions=True)

	def test_an_edit_keeps_the_answers_as_saved_not_a_repeated_row(self):
		sign_up = self.sign_up(answer_rows("", diet="None", shirt_size="Small"))
		saved = self.get_answer_rows(sign_up.name)
		registrant = sign_up.attendees[0].name

		sign_up.append(
			"answers",
			{"attendee": registrant, "question": "shirt_size", "label": "Forged", "answer": "Not a choice"},
		)
		sign_up.append("answers", {"attendee": registrant, "question": "shirt_size", "answer": "Small"})
		sign_up.save(ignore_permissions=True)

		self.assertEqual(self.get_answer_rows(sign_up.name), saved)

	def test_a_changed_attendee_row_answers_again(self):
		sign_up = self.sign_up(
			answer_rows("", diet="None") + answer_rows("kid-row-04", diet="Vegan"),
			[{"name": "kid-row-04", "attendee_name": "_Test Kid"}],
		)
		question_set = frappe.get_doc("Question Set", self.question_set)
		question_set.append("questions", {"label": "Allergies", "question_type": "Data", "is_required": 1})
		question_set.save(ignore_permissions=True)

		sign_up.reload()
		next(row for row in sign_up.attendees if row.name == "kid-row-04").attendee_name = "_Test Other Kid"
		with self.assertRaises(frappe.MandatoryError):
			sign_up.save(ignore_permissions=True)

	def test_the_answers_of_a_removed_attendee_go_with_the_row(self):
		sign_up = self.sign_up(
			answer_rows("", diet="None") + answer_rows("kid-row-03", diet="Vegan"),
			[{"name": "kid-row-03", "attendee_name": "_Test Kid"}],
		)

		sign_up.attendees = [row for row in sign_up.attendees if row.name != "kid-row-03"]
		sign_up.save(ignore_permissions=True)

		self.assertEqual(
			[attendee for attendee, _question in self.get_answers(sign_up.name)], [sign_up.attendees[0].name]
		)

	def test_a_change_made_by_code_keeps_the_answers(self):
		sign_up = self.sign_up(answer_rows("", diet="None"))
		before = self.get_answers(sign_up.name)

		sign_up.cancel_registration()

		self.assertEqual(self.get_answers(sign_up.name), before)


class TestRegisterAnswers(AnswersTestCase):
	def register(self, answers, **values):
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.church)
		try:
			return sign_up(
				self.function,
				registrant_name="_Test Rhea Register",
				email="_test_rhea@example.com",
				answers=json.dumps(answers),
				**values,
			)
		finally:
			frappe.set_user("Administrator")

	def get_sign_up(self):
		return frappe.get_doc(SIGN_UP, {"function": self.function, "registrant_name": "_Test Rhea Register"})

	def test_the_registrant_answers_with_the_empty_key(self):
		self.register({"": {"diet": "Gluten free", "shirt_size": "Small"}})

		sign_up = self.get_sign_up()
		self.assertEqual(
			{(row.attendee, row.question, row.answer) for row in sign_up.answers},
			{
				(sign_up.attendees[0].name, "diet", "Gluten free"),
				(sign_up.attendees[0].name, "shirt_size", "Small"),
			},
		)

	def test_each_attendee_answers_by_their_person_or_typed_name(self):
		member = make_person("_Test Household", "Child").name
		attendees = [
			{"person": member, "attendee_name": "_Test Household Child"},
			{"attendee_name": "_Test Friend"},
		]
		answers = {"": {"diet": "None"}, member: {"diet": "Nut free"}, "_Test Friend": {"diet": "Vegan"}}

		rows = get_answer_rows(
			frappe.get_doc("Function", self.function), {"answers": json.dumps(answers)}, attendees
		)

		member_row, friend_row = (attendee["name"] for attendee in attendees)
		self.assertEqual(
			{(row["attendee"], row["answer"]) for row in rows},
			{("", "None"), (member_row, "Nut free"), (friend_row, "Vegan")},
		)
		sign_up = self.sign_up(rows, attendees)
		registrant = next(
			row.name
			for row in sign_up.attendees
			if not row.person and row.attendee_name == "_Test Ana Answer"
		)
		self.assertEqual(
			{row.attendee: row.answer for row in sign_up.answers},
			{registrant: "None", member_row: "Nut free", friend_row: "Vegan"},
		)

	def test_a_guest_answers_for_each_person_who_comes(self):
		self.register(
			{"": {"diet": "None"}, "_Test Friend": {"diet": "Vegan"}},
			attendees=json.dumps([{"attendee_name": "_Test Friend"}]),
		)

		sign_up = self.get_sign_up()
		names = {row.attendee_name: row.name for row in sign_up.attendees}
		self.assertEqual(
			{row.attendee: row.answer for row in sign_up.answers},
			{names["_Test Rhea Register"]: "None", names["_Test Friend"]: "Vegan"},
		)

	def test_a_required_question_left_blank_refuses_the_registration(self):
		with self.assertRaises(frappe.MandatoryError):
			self.register({"": {"shirt_size": "Small"}})

	def test_answers_for_someone_not_attending_or_in_the_wrong_shape_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.register({"": {"diet": "None"}, "_Test Stranger": {"diet": "None"}})
		with self.assertRaises(frappe.ValidationError):
			self.register({"": ["None"]})

	def test_a_guest_reads_the_questions_only_of_a_function_open_to_guests(self):
		members_only = make_function(
			"_Test Members Camp", start_date="2031-06-01", allow_sign_ups=1, publish=1
		)
		members_only.db_set("question_set", self.question_set)
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.church)

		self.assertEqual(
			[field["fieldname"] for field in get_questions(self.function)], ["diet", "shirt_size"]
		)
		self.assertRaises(frappe.PermissionError, get_questions, members_only.name)


class TestAnonymizeSignUpAnswers(AnswersTestCase):
	def test_an_anonymized_attendee_loses_their_answers_and_name_and_the_others_keep_theirs(self):
		person = make_person("_Test Pat", "Attendee").name
		sign_up = self.sign_up(
			answer_rows("", diet="None") + answer_rows("pat-row-01", diet="Pat needs no nuts"),
			[{"name": "pat-row-01", "person": person}],
		)
		sign_up.notes = "_Test changed once"
		sign_up.save(ignore_permissions=True, ignore_version=False)

		anonymize(person)

		sign_up.reload()
		registrant = next(row.name for row in sign_up.attendees if row.name != "pat-row-01")
		self.assertEqual([attendee for attendee, _question in self.get_answers(sign_up.name)], [registrant])
		self.assertEqual(sign_up.registrant_name, "_Test Ana Answer")
		self.assertNotIn("_Test Pat Attendee", frappe.as_json(sign_up.as_dict()))
		history = frappe.get_all(
			"Version", filters={"ref_doctype": SIGN_UP, "docname": sign_up.name}, pluck="data"
		)
		self.assertNotIn("Pat needs no nuts", "".join(history))

	def test_an_anonymized_registrant_keeps_no_phone_email_or_typed_name(self):
		person = make_person("_Test Reg", "Istrant").name
		sign_up = self.sign_up(
			answer_rows("", diet="None"),
			person=person,
			registrant_name="_Test Reggie",
			phone="555 0199",
		)

		anonymize(person)

		values = frappe.db.get_value(SIGN_UP, sign_up.name, ["phone", "email", "registrant_name"])
		self.assertEqual(values, (None, None, None))
		self.assertEqual(self.get_answers(sign_up.name), {})

	def test_an_anonymized_person_keeps_nothing_on_a_guest_sign_up_left_unlinked(self):
		person = make_person(
			"_Test Una", "Linked", emails=[{"email_address": "_test_una_linked@example.com"}]
		).name
		sign_up = self.sign_up(
			answer_rows("", diet="None"),
			registrant_name="_Test Una Linked",
			email="_TEST_Una_Linked@example.com",
			phone="555 0198",
		)
		sign_up.add_comment("Comment", "_Test not linked to the person")

		anonymize(person)

		sign_up.reload()
		self.assertEqual((sign_up.registrant_name, sign_up.email, sign_up.phone), (None, None, None))
		self.assertEqual([row.attendee_name for row in sign_up.attendees], ["Anonymized"])
		self.assertEqual(sign_up.answers, [])
		self.assertTrue(sign_up.title.endswith(" - Anonymized"))
		self.assertNotIn("Una", frappe.as_json(sign_up.as_dict()))
		self.assertFalse(
			frappe.db.exists("Comment", {"reference_doctype": SIGN_UP, "reference_name": sign_up.name})
		)


class TestQuestionSetChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.theirs = make_question_set("_Test Their Questions", church=cls.other_church).name
		cls.shared = make_question_set("_Test Shared Questions", church=cls.other_church, is_shared=1).name

	def test_a_function_asks_only_its_churchs_or_a_shared_question_set(self):
		with self.assertRaises(frappe.PermissionError):
			make_function("_Test Their Set Camp", church=self.church, question_set=self.theirs)

		function = make_function("_Test Shared Set Camp", church=self.church, question_set=self.shared)
		self.assertEqual(function.question_set, self.shared)

	def test_a_save_that_leaves_the_set_alone_is_not_checked_again(self):
		function = make_function("_Test Unchanged Set Camp", church=self.church)
		function.db_set("question_set", self.theirs)

		function.reload()
		function.description = "_Test an attendance save, say"
		function.save(ignore_permissions=True)
