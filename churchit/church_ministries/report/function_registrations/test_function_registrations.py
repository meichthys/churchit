# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe

from churchit.church_ministries.report.function_registrations.function_registrations import execute
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

SIGN_UP = "Function Sign-Up"
QUESTIONS = [
	{"label": "Diet", "question_type": "Data", "is_required": 1},
	{"label": "Shirt size", "question_type": "Select", "options": "Small\nLarge"},
]


def make_sign_up(function, registrant_name, attendees=(), answers=(), **values):
	return frappe.get_doc(
		{
			"doctype": SIGN_UP,
			"function": function,
			"registrant_name": registrant_name,
			"email": "_test_registrations@example.com",
			"attendees": list(attendees),
			"answers": list(answers),
			**values,
		}
	).insert(ignore_permissions=True, set_child_names=False)


class TestFunctionRegistrations(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		cls.addClassCleanup(enqueue.stop)

		question_set = frappe.get_doc(
			{
				"doctype": "Question Set",
				"title": "_Test Roster Questions",
				"church": cls.church,
				"questions": QUESTIONS,
			}
		).insert(ignore_permissions=True)
		function = make_function(
			"_Test Roster Camp", church=cls.church, allow_sign_ups=1, question_set=question_set.name
		)
		function.append("selections", {"selection": "Adult"})
		function.append("selections", {"selection": "Child"})
		function.save(ignore_permissions=True)
		cls.function = function.name
		cls.sign_up = make_sign_up(
			cls.function,
			"_Test Rosa Roster",
			[
				{"name": "roster-rosa-01", "attendee_name": "_Test Rosa Roster", "selection": "Adult"},
				{"name": "roster-kid-01", "attendee_name": "_Test Roster Kid", "selection": "Child"},
			],
			[
				{"attendee": "roster-rosa-01", "question": "diet", "answer": "None"},
				{"attendee": "roster-rosa-01", "question": "shirt_size", "answer": "Large"},
				{"attendee": "roster-kid-01", "question": "diet", "answer": "Vegan"},
			],
		).name
		cls.other_function = make_function(
			"_Test Other Roster Camp", church=cls.other_church, allow_sign_ups=1
		).name
		cls.other_sign_up = make_sign_up(cls.other_function, "_Test Otto Other").name

	def rows(self, **filters):
		columns, data = execute(filters)
		return columns, [row for row in data if row.sign_up in (self.sign_up, self.other_sign_up)]

	def test_one_row_per_attendee_with_a_column_per_question(self):
		columns, data = self.rows(function=self.function)

		self.assertEqual(
			[(column["fieldname"], column["label"]) for column in columns[-2:]],
			[("answer_diet", "Diet"), ("answer_shirt_size", "Shirt size")],
		)
		self.assertEqual(
			[
				(row.attendee_name, row.selection, row.status, row.answer_diet, row.get("answer_shirt_size"))
				for row in data
			],
			[
				("_Test Rosa Roster", "Adult", "Confirmed", "None", "Large"),
				("_Test Roster Kid", "Child", "Confirmed", "Vegan", None),
			],
		)

	def test_the_status_filter_and_no_function_filter(self):
		_columns, data = self.rows()
		self.assertEqual({row.sign_up for row in data}, {self.sign_up, self.other_sign_up})

		_columns, data = self.rows(status="Cancelled")
		self.assertEqual(data, [])

	def test_a_church_manager_sees_no_attendee_of_another_churchs_function(self):
		manager = ensure_user("_test_registrations_b@example.com", "RosterB", roles=("Church Manager",))
		make_person("RosterB", "Manager", church=self.other_church, user=manager)
		frappe.set_user(manager)

		_columns, data = self.rows()
		self.assertEqual({row.sign_up for row in data}, {self.other_sign_up})
		self.assertRaises(frappe.PermissionError, self.rows, function=self.function)
