# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype

from churchit.church_people.merge import merge_people
from churchit.church_people.privacy import anonymize
from churchit.questions import NO, YES, get_fields, set_answers, validate_answers
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, force_single_church, make_person

QUESTIONS = [
	{"label": "Your name", "question_type": "Data", "is_required": 1},
	{"label": "Anything else?", "question_type": "Small Text"},
	{"label": "T-shirt size", "question_type": "Select", "options": "Small\nMedium\nLarge"},
	{"label": "Needs a ride", "question_type": "Check"},
	{"label": "Agrees to the rules", "question_type": "Check", "is_required": 1},
	{"label": "Birth date", "question_type": "Date"},
	{"label": "Nights", "question_type": "Int"},
	{"label": "Parent email", "question_type": "Email"},
	{"label": "Parent phone", "question_type": "Phone"},
]
ANSWERS = {"your_name": "Ann", "agrees_to_the_rules": 1}


def make_question_set(title, questions=QUESTIONS, **values):
	return frappe.get_doc(
		{"doctype": "Question Set", "title": title, "questions": questions, **values}
	).insert(ignore_permissions=True)


def drop_doctype(doctype):
	"""Delete the test *doctype* and its table, for good."""
	frappe.delete_doc_if_exists("DocType", doctype, force=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{doctype}`")
	frappe.flags.link_fields = None


class TestQuestions(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		cls.question_set = make_question_set("_Test Camp Questions").name

	def test_answer_names_are_made_from_the_questions(self):
		names = [row.fieldname for row in frappe.get_doc("Question Set", self.question_set).questions]

		self.assertEqual(names[:3], ["your_name", "anything_else", "t_shirt_size"])

	def test_two_questions_cannot_share_an_answer_name(self):
		with self.assertRaises(frappe.ValidationError):
			make_question_set("_Test Twice", [{"label": "Size"}, {"label": "size?"}])

	def test_a_choice_question_needs_its_choices(self):
		with self.assertRaises(frappe.ValidationError):
			make_question_set("_Test No Choices", [{"label": "Size", "question_type": "Select"}])

	def test_each_question_type_has_its_field(self):
		fields = {field["fieldname"]: field for field in get_fields(self.question_set)}

		self.assertEqual(fields["your_name"]["reqd"], 1)
		self.assertEqual(fields["t_shirt_size"]["options"], "\nSmall\nMedium\nLarge")
		self.assertEqual(
			(fields["parent_email"]["fieldtype"], fields["parent_email"]["options"]), ("Data", "Email")
		)
		self.assertEqual(
			(fields["parent_phone"]["fieldtype"], fields["parent_phone"]["options"]), ("Data", "Phone")
		)
		self.assertEqual(
			[fields[name]["fieldtype"] for name in ("anything_else", "needs_a_ride", "birth_date", "nights")],
			["Small Text", "Check", "Date", "Int"],
		)

	def test_answers_are_kept_as_text_in_question_order(self):
		answers = {
			**ANSWERS,
			"nights": "2",
			"needs_a_ride": "0",
			"birth_date": "2012-05-01",
			"t_shirt_size": "Medium",
			"anything_else": " ",
		}

		kept = validate_answers(self.question_set, answers)

		self.assertEqual(
			kept,
			{
				"your_name": "Ann",
				"t_shirt_size": "Medium",
				"needs_a_ride": NO,
				"agrees_to_the_rules": YES,
				"birth_date": "2012-05-01",
				"nights": "2",
			},
		)
		self.assertEqual(
			list(kept),
			["your_name", "t_shirt_size", "needs_a_ride", "agrees_to_the_rules", "birth_date", "nights"],
		)

	def test_a_required_question_left_blank_is_refused(self):
		for missing in ({"your_name": ""}, {"agrees_to_the_rules": 0}):
			with self.subTest(missing), self.assertRaises(frappe.MandatoryError):
				validate_answers(self.question_set, {**ANSWERS, **missing})

	def test_an_answer_to_a_question_not_asked_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			validate_answers(self.question_set, {**ANSWERS, "allergies": "None"})

	def test_an_answer_that_does_not_fit_its_question_is_refused(self):
		for wrong in (
			{"t_shirt_size": "Huge"},
			{"nights": "two"},
			{"parent_email": "not an address"},
			{"parent_phone": "call me"},
			{"birth_date": "someday"},
		):
			with self.subTest(wrong), self.assertRaises(frappe.ValidationError):
				validate_answers(self.question_set, {**ANSWERS, **wrong})


class TestAnswersOnARecord(RollbackEachTest):
	"""Answers on a record that names a person, the way a registration will keep them."""

	doctype = "Test Question Answer Owner"
	attendee_doctype = "Test Question Answer Attendee"

	@classmethod
	def setUpClass(cls):
		# Cleanups run last first, so these run after the class's rollback.
		cls.addClassCleanup(drop_doctype, cls.attendee_doctype)
		cls.addClassCleanup(drop_doctype, cls.doctype)
		super().setUpClass()
		# Making a doctype commits, so it comes before every other write of the class.
		drop_doctype(cls.doctype)
		drop_doctype(cls.attendee_doctype)
		person = {"fieldname": "person", "fieldtype": "Link", "options": "Person", "label": "Person"}
		new_doctype(cls.attendee_doctype, fields=[person], istable=1).insert()
		new_doctype(
			cls.doctype,
			fields=[
				person,
				{"fieldname": "attendees", "fieldtype": "Table", "options": cls.attendee_doctype},
				{"fieldname": "answers", "fieldtype": "Table", "options": "Question Answer"},
			],
			track_changes=1,
		).insert()
		frappe.flags.link_fields = None
		force_single_church()
		ensure_root_church()
		cls.question_set = make_question_set("_Test Record Questions").name

	def make_record(self, person=None, attendees=()):
		doc = frappe.new_doc(self.doctype)
		doc.person = person
		doc.set("attendees", [{"person": attendee} for attendee in attendees])
		set_answers(doc, self.question_set, ANSWERS)
		doc.insert()
		# A change after the insert keeps the answers in the record's history.
		set_answers(doc, self.question_set, {**ANSWERS, "parent_email": "ann.parent@example.com"})
		return doc.save(ignore_version=False)

	def get_history(self, record):
		return frappe.get_all(
			"Version", filters={"ref_doctype": self.doctype, "docname": record}, pluck="data"
		)

	def get_answers(self, record):
		return frappe.get_all(
			"Question Answer",
			filters={"parenttype": self.doctype, "parent": record},
			fields=["label", "answer"],
			order_by="idx",
		)

	def test_answers_keep_the_question_as_it_was_asked(self):
		record = self.make_record(make_person("_Test Answering", "Person").name)

		self.assertEqual(
			[(row.label, row.answer) for row in self.get_answers(record.name)],
			[
				("Your name", "Ann"),
				("Needs a ride", NO),
				("Agrees to the rules", YES),
				("Parent email", "ann.parent@example.com"),
			],
		)

	def test_anonymizing_the_person_clears_their_answers(self):
		person = make_person("_Test Anonymized", "Answerer").name
		record = self.make_record(person)

		self.assertIn("ann.parent@example.com", "".join(self.get_history(record.name)))

		anonymize(person)

		self.assertEqual(self.get_answers(record.name), [])
		self.assertNotIn("ann.parent@example.com", "".join(self.get_history(record.name)))

	def test_a_group_keeps_its_answers_when_one_attendee_is_anonymized(self):
		person = make_person("_Test Anonymized", "Attendee").name
		record = self.make_record(attendees=[person, make_person("_Test Other", "Attendee").name])

		anonymize(person)

		self.assertEqual(len(self.get_answers(record.name)), 4)

	def test_a_merge_keeps_the_answers(self):
		kept, removed = make_person("_Test Merge", "Kept").name, make_person("_Test Merge", "Removed").name
		record = self.make_record(removed)

		merge_people(kept, removed)

		self.assertEqual(frappe.db.get_value(self.doctype, record.name, "person"), kept)
		self.assertEqual(len(self.get_answers(record.name)), 4)
