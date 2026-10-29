# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.tests.helpers import RollbackEachTest, ensure_root_church, force_single_church, make_person
from churchit.tests.test_questions import make_question_set

QUESTIONS = [
	{"label": "Expected guests", "question_type": "Int", "is_required": 1},
	{"label": "Needs sound", "question_type": "Check"},
]


class TestSetupSheet(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		cls.requester = make_person("_Test Sheet", "Requester").name
		cls.room = (
			frappe.get_doc(
				{
					"doctype": "Room",
					"room_name": "_Test Sheet Hall",
					"is_bookable": 1,
					"question_set": make_question_set("_Test Sheet Questions", QUESTIONS).name,
					"setups": [
						{"setup_name": "Banquet", "capacity": 80, "description": "Round tables of eight"}
					],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
		cls.asset = (
			frappe.get_doc({"doctype": "Church Asset", "title": "_Test Sheet Projector", "is_bookable": 1})
			.insert(ignore_permissions=True)
			.name
		)

	def tearDown(self):
		for name in frappe.get_all("Room Booking", filters={"room": self.room}, pluck="name"):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
		super().tearDown()

	def test_the_sheet_shows_the_room_times_setup_equipment_and_answers(self):
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": self.room,
				"requester": self.requester,
				"purpose": "_Test Sheet Dinner",
				"start_datetime": "2036-05-06 18:00:00",
				"end_datetime": "2036-05-06 21:00:00",
				"setup": "Banquet",
				"setup_notes": "Stage at the north wall",
				"assets": [{"asset": self.asset}],
				"answers": [{"question": "expected_guests", "answer": "40"}],
			}
		).insert(ignore_permissions=True)

		html = frappe.get_print("Room Booking", booking.name, "Setup Sheet")

		for text in (
			"_Test Sheet Hall",
			"_Test Sheet Dinner",
			"_Test Sheet Requester",
			booking.get_formatted("start_datetime"),
			booking.get_formatted("end_datetime"),
			"Banquet",
			"<td>80</td>",
			"Round tables of eight",
			"Stage at the north wall",
			"_Test Sheet Projector",
			"Expected guests",
			'<td class="text">40</td>',
			"Needs sound",
		):
			self.assertIn(text, html)
