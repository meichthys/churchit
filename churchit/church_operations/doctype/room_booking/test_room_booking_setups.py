# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_foundations.church_access import set_user_church
from churchit.church_operations.doctype.room_booking.room_booking import get_room_questions
from churchit.questions import get_fields
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)
from churchit.tests.test_questions import make_question_set

SETUP_QUESTIONS = [
	{"label": "Expected guests", "question_type": "Int", "is_required": 1},
	{"label": "Needs sound", "question_type": "Check"},
]
CATERING_QUESTIONS = [{"label": "Catering", "question_type": "Data"}]
TICK_QUESTIONS = [
	{"label": "Agree", "question_type": "Check", "is_required": 1},
	{"label": "Needs sound", "question_type": "Check"},
]
TICKED = [{"question": "agree", "answer": "1"}, {"question": "needs_sound", "answer": "1"}]


def make_room(room_name, **values):
	return frappe.get_doc({"doctype": "Room", "room_name": room_name, "is_bookable": 1, **values}).insert(
		ignore_permissions=True
	)


class BookingTestCase(RollbackEachTest):
	"""Bookings of this class's rooms, deleted after each test."""

	rooms = ()

	def tearDown(self):
		super().tearDown()
		for name in frappe.get_all("Room Booking", filters={"room": ["in", self.rooms]}, pluck="name"):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)

	def book(self, room, **values):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.requester,
				"purpose": "_Test A3 booking",
				"start_datetime": "2032-05-06 09:00:00",
				"end_datetime": "2032-05-06 10:00:00",
				**values,
			}
		).insert(ignore_permissions=True)


class TestRoomSetups(BookingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		cls.requester = make_person("_Test A3", "Setup Booker").name
		cls.hall = make_room(
			"_Test A3 Setup Hall",
			setups=[{"setup_name": "Banquet"}, {"setup_name": "Theatre", "capacity": 80}],
		).name
		cls.chapel = make_room("_Test A3 Setup Chapel", setups=[{"setup_name": "Circle"}]).name
		cls.rooms = (cls.hall, cls.chapel)

	def test_a_room_refuses_two_setups_with_one_name(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Banquet"):
			make_room("_Test A3 Twice", setups=[{"setup_name": "Banquet"}, {"setup_name": "Banquet"}])

	def test_a_booking_takes_a_setup_of_its_room(self):
		self.assertEqual(self.book(self.hall, setup="Theatre", setup_notes="Two aisles").setup, "Theatre")

	def test_a_setup_that_is_not_on_the_room_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "is not a setup of"):
			self.book(self.hall, setup="Circle")

		booking = self.book(self.chapel, setup="Circle")
		booking.room = self.hall
		with self.assertRaisesRegex(frappe.ValidationError, "is not a setup of"):
			booking.save()

	def test_a_setup_needs_a_room(self):
		asset = ensure("Church Asset", {"title": "_Test A3 Projector"}, {"title": "_Test A3 Projector"})
		frappe.db.set_value("Church Asset", asset, "is_bookable", 1)
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"assets": [{"asset": asset}],
				"requester": self.requester,
				"purpose": "_Test A3 no room",
				"start_datetime": "2032-05-07 09:00:00",
				"end_datetime": "2032-05-07 10:00:00",
				"setup": "Banquet",
			}
		)
		self.addCleanup(frappe.db.delete, "Room Booking", {"purpose": "_Test A3 no room"})
		with self.assertRaisesRegex(frappe.ValidationError, "Choose a room for the setup"):
			booking.insert(ignore_permissions=True)

	def test_a_setup_taken_off_the_room_keeps_the_booking_editable(self):
		booking = self.book(self.chapel, setup="Circle")
		room = frappe.get_doc("Room", self.chapel)
		room.setups = []
		room.save()

		booking.reload()
		booking.notes = "Bring chairs"
		booking.save()
		self.assertEqual(booking.setup, "Circle")


class TestRoomQuestions(BookingTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		cls.requester = make_person("_Test A3", "Question Booker").name
		cls.setup_set = make_question_set("_Test A3 Setup Questions", SETUP_QUESTIONS).name
		cls.catering_set = make_question_set("_Test A3 Catering Questions", CATERING_QUESTIONS).name
		cls.hall = make_room("_Test A3 Question Hall", question_set=cls.setup_set).name
		cls.chapel = make_room("_Test A3 Question Chapel", question_set=cls.catering_set).name
		cls.plain_room = make_room("_Test A3 Plain Room").name
		cls.tick_set = make_question_set("_Test A3 Tick Questions", TICK_QUESTIONS).name
		cls.tick_hall = make_room("_Test A3 Tick Hall", question_set=cls.tick_set).name
		cls.tick_chapel = make_room("_Test A3 Tick Chapel", question_set=cls.tick_set).name
		cls.gated_hall = make_room(
			"_Test A3 Gated Hall", question_set=cls.catering_set, requires_approval=1
		).name
		cls.rooms = (cls.hall, cls.chapel, cls.plain_room, cls.tick_hall, cls.tick_chapel, cls.gated_hall)

	def stored_answers(self, booking):
		return frappe.get_all(
			"Question Answer",
			filters={"parenttype": "Room Booking", "parent": booking.name},
			fields=["question", "label", "answer"],
			order_by="idx",
		)

	def test_get_room_questions_returns_the_fields_of_the_rooms_set(self):
		self.assertEqual(get_room_questions(self.hall), get_fields(self.setup_set))
		self.assertEqual(get_room_questions(self.plain_room), [])

	def test_a_required_question_with_no_answer_refuses_the_save(self):
		with self.assertRaisesRegex(frappe.MandatoryError, "Expected guests"):
			self.book(self.hall)

	def test_the_answers_are_question_answer_rows_of_the_booking(self):
		booking = self.book(self.hall, answers=[{"question": "expected_guests", "answer": "40"}])
		self.assertEqual(
			self.stored_answers(booking),
			[
				{"question": "expected_guests", "label": "Expected guests", "answer": "40"},
				{"question": "needs_sound", "label": "Needs sound", "answer": "No"},
			],
		)

	def test_an_answer_to_a_question_the_room_does_not_ask_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "not questions of this Question Set"):
			self.book(
				self.hall,
				answers=[{"question": "expected_guests", "answer": "4"}, {"question": "x", "answer": "1"}],
			)
		with self.assertRaisesRegex(frappe.ValidationError, "asks no questions"):
			self.book(self.plain_room, answers=[{"question": "x", "answer": "1"}])

	def test_a_change_of_room_to_another_set_clears_the_old_rows(self):
		booking = self.book(self.hall, answers=[{"question": "expected_guests", "answer": "40"}])
		booking.room = self.chapel
		booking.save()
		self.assertEqual(self.stored_answers(booking), [])

		booking.room = self.hall
		booking.answers = []
		booking.append("answers", {"question": "expected_guests", "answer": "12"})
		booking.save()
		booking.room = self.plain_room
		booking.save()
		self.assertEqual(booking.answers, [])
		self.assertEqual(self.stored_answers(booking), [])

	def test_a_change_of_the_rooms_set_keeps_the_old_rows_until_new_answers(self):
		booking = self.book(self.hall, answers=[{"question": "expected_guests", "answer": "40"}])
		frappe.db.set_value("Room", self.hall, "question_set", self.tick_set)
		self.addCleanup(frappe.db.set_value, "Room", self.hall, "question_set", self.setup_set)

		booking.reload()
		booking.notes = "Bring chairs"
		booking.save()
		self.assertEqual(
			[row.question for row in self.stored_answers(booking)], ["expected_guests", "needs_sound"]
		)

		booking.answers = []
		booking.append("answers", {"question": "agree", "answer": "1"})
		booking.save()
		self.assertEqual([row.answer for row in self.stored_answers(booking)], ["Yes", "No"])

	def test_a_block_denies_a_request_with_answers_to_an_old_set(self):
		request = self.book(self.gated_hall, answers=[{"question": "catering", "answer": "Soup"}])
		self.assertEqual(request.status, "Requested")
		frappe.db.set_value("Room", self.gated_hall, "question_set", self.tick_set)
		self.addCleanup(frappe.db.set_value, "Room", self.gated_hall, "question_set", self.catering_set)

		self.book(
			self.gated_hall,
			status="Blocked",
			requester=None,
			start_datetime="2032-05-06 08:00:00",
			end_datetime="2032-05-06 12:00:00",
		)
		self.assertEqual(frappe.db.get_value("Room Booking", request.name, "status"), "Denied")
		self.assertEqual([row.answer for row in self.stored_answers(request)], ["Soup"])

	def test_a_blocked_time_keeps_no_answers(self):
		block = self.book(
			self.tick_hall,
			status="Blocked",
			requester=None,
			answers=[{"question": "agree", "answer": "0"}],
			start_datetime="2032-05-07 08:00:00",
			end_datetime="2032-05-07 12:00:00",
		)
		self.assertEqual(self.stored_answers(block), [])

	def test_a_copy_keeps_the_ticks(self):
		booking = self.book(self.tick_hall, answers=TICKED)
		# As recurrence.copy_room_bookings copies a booking.
		copy = frappe.copy_doc(booking)
		copy.start_datetime = "2032-05-13 09:00:00"
		copy.end_datetime = "2032-05-13 10:00:00"
		copy.insert(ignore_permissions=True)
		self.assertEqual([row.answer for row in self.stored_answers(copy)], ["Yes", "Yes"])

	def test_a_move_to_a_room_with_the_same_set_keeps_the_ticks(self):
		booking = self.book(self.tick_hall, answers=TICKED)
		booking.room = self.tick_chapel
		booking.save()
		self.assertEqual([row.answer for row in self.stored_answers(booking)], ["Yes", "Yes"])

	def test_a_change_of_room_keeps_the_answers_given_for_the_new_room(self):
		booking = self.book(self.chapel, answers=[{"question": "catering", "answer": "Soup"}])
		booking.room = self.hall
		booking.answers = []
		booking.append("answers", {"question": "expected_guests", "answer": "25"})
		booking.save()
		self.assertEqual(
			[row.question for row in self.stored_answers(booking)], ["expected_guests", "needs_sound"]
		)

	def test_a_later_save_keeps_the_answer_rows(self):
		booking = self.book(self.hall, answers=[{"question": "expected_guests", "answer": "40"}])
		rows = [row.name for row in booking.answers]
		booking.notes = "Bring chairs"
		booking.save()
		self.assertEqual([row.name for row in booking.answers], rows)


class TestRoomQuestionsAcrossChurches(BookingTestCase):
	"""get_room_questions answers only for a room the reader may read."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.staff_b = ensure_user("_test_a3_staff_b@example.com", "A3 Staff B", roles=("Church Staff",))
		set_user_church(cls.staff_b, cls.branch_b)
		cls.manager_b = ensure_user(
			"_test_a3_manager_b@example.com", "A3 Manager B", roles=("Church Manager",)
		)
		set_user_church(cls.manager_b, cls.branch_b)
		cls.question_set = make_question_set(
			"_Test A3 Branch Questions", CATERING_QUESTIONS, church=cls.branch_a
		).name
		cls.room_a = make_room(
			"_Test A3 Branch A Hall", church=cls.branch_a, question_set=cls.question_set
		).name
		cls.shared_room = make_room(
			"_Test A3 Shared Hall", church=cls.branch_a, is_shared=1, question_set=cls.question_set
		).name

	def questions_as(self, user, room):
		frappe.set_user(user)
		try:
			return get_room_questions(room)
		finally:
			frappe.set_user("Administrator")

	def test_another_churchs_room_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.questions_as(self.staff_b, self.room_a)

	def test_a_shared_room_asks_every_church(self):
		self.assertEqual(self.questions_as(self.staff_b, self.shared_room), get_fields(self.question_set))

	def test_a_room_refuses_another_churchs_question_set(self):
		shared_set = make_question_set(
			"_Test A3 Shared Questions", CATERING_QUESTIONS, church=self.branch_a, is_shared=1
		).name
		frappe.set_user(self.manager_b)
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaisesRegex(frappe.PermissionError, "belongs to another church"):
			make_room("_Test A3 Branch B Hall", question_set=self.question_set)
		room = make_room("_Test A3 Branch B Hall", question_set=shared_set)
		self.assertEqual((room.church, room.question_set), (self.branch_b, shared_set))
