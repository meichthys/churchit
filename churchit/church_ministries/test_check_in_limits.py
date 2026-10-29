# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
import frappe.client
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, now_datetime, today

from churchit.church_ministries.check_in_limits import (
	RoomFullError,
	get_bound_problem,
	get_bound_problems,
	get_capacity,
	get_rooms,
)
from churchit.church_ministries.doctype.function_check_in.function_check_in import add_check_ins
from churchit.church_ministries.page.check_in.check_in import check_in
from churchit.church_ministries.recurrence import create_occurrence
from churchit.church_people.derived import FINAL_GRADE
from churchit.church_people.test_derived import set_school_year_start_month
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
	set_private_people,
)

# make_function's default start date, on which every bound is measured.
START = "2031-05-01"


def graduation_year_in(grade):
	"""The graduation year of a child in *grade* on START, with a school year that starts in August."""
	return getdate(START).year + FINAL_GRADE - grade


def born_years_before_start(years):
	ensure("Life Event Type", {"type": "Birth"})
	return [{"event_type": "Birth", "date": add_days(f"{getdate(START).year - years}-05-01", -1)}]


class TestBoundProblem(RollbackEachTest):
	def setUp(self):
		super().setUp()
		month = frappe.db.get_single_value("People Settings", "school_year_start_month")
		set_school_year_start_month("August")
		self.addCleanup(set_school_year_start_month, month)

	def test_a_grade_6_child_is_outside_kindergarten_to_grade_5(self):
		function = make_function("_Test Bound K to 5", min_grade="Kindergarten", max_grade="Grade 5")
		sixth = make_person("Sixer", "_Test Bounds", graduation_year=graduation_year_in(6))
		fifth = make_person("Fifer", "_Test Bounds", graduation_year=graduation_year_in(5))
		kindergarten = make_person("Kinder", "_Test Bounds", graduation_year=graduation_year_in(0))

		self.assertIn("Grade 6", get_bound_problem(function.name, sixth.name))
		self.assertIsNone(get_bound_problem(function.name, fifth.name))
		self.assertIsNone(get_bound_problem(function.name, kindergarten.name))

	def test_a_preschooler_or_a_child_with_no_graduation_year_is_outside_a_grade_bound(self):
		function = make_function("_Test Bound Grade 1 up", min_grade="Grade 1")
		preschooler = make_person("Tiny", "_Test Bounds", graduation_year=graduation_year_in(-1))
		unknown = make_person("Nogrid", "_Test Bounds")

		self.assertIsNotNone(get_bound_problem(function.name, preschooler.name))
		self.assertIsNotNone(get_bound_problem(function.name, unknown.name))

	def test_a_child_with_no_birth_date_is_outside_a_max_age(self):
		function = make_function("_Test Bound Under 11", max_age=10)
		unknown = make_person("Noage", "_Test Bounds")
		ten = make_person("Tenner", "_Test Bounds", life_events=born_years_before_start(10))
		eleven = make_person("Eleven", "_Test Bounds", life_events=born_years_before_start(11))

		self.assertIsNotNone(get_bound_problem(function.name, unknown.name))
		self.assertIsNone(get_bound_problem(function.name, ten.name))
		self.assertIn("11", get_bound_problem(function.name, eleven.name))

	def test_a_child_under_the_youngest_age_has_a_problem(self):
		function = make_function("_Test Bound 4 up", min_age=4)
		three = make_person("Three", "_Test Bounds", life_events=born_years_before_start(3))
		four = make_person("Four", "_Test Bounds", life_events=born_years_before_start(4))

		self.assertIn("3", get_bound_problem(function.name, three.name))
		self.assertIsNone(get_bound_problem(function.name, four.name))

	def test_a_function_with_no_bounds_takes_anyone(self):
		function = make_function("_Test Bound None")
		self.assertIsNone(get_bound_problem(function.name, make_person("Anyone", "_Test Bounds").name))

	def test_a_recurring_copy_keeps_its_bounds(self):
		start = add_days(getdate(), -7)
		bounds = {"min_age": 4, "max_age": 11, "min_grade": "Kindergarten", "max_grade": "Grade 5"}
		template = make_function(
			"_Test Bound Weekly",
			start_date=start,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week=start.strftime("%A"),
			repeat_horizon_weeks=8,
			**bounds,
		)

		occurrence = create_occurrence(template, add_days(start, 7))

		self.assertEqual({field: occurrence.get(field) for field in bounds}, bounds)


class TestBoundProblemsAtTheStation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_root_church()
		set_multi_church(True)
		cls.branch_a = make_branch("_Test Bounds A", "TBDA")
		cls.branch_b = make_branch("_Test Bounds B", "TBDB")
		cls.volunteer_a = cls.bind_volunteer("_test_bounds_a@example.com", "BoundsA", cls.branch_a)
		cls.volunteer_b = cls.bind_volunteer("_test_bounds_b@example.com", "BoundsB", cls.branch_b)
		cls.function = make_function("_Test Bounds Class", church=cls.branch_a, max_age=10)
		cls.child_a = make_person("Abby", "_Test Bounds Child", church=cls.branch_a).name
		cls.child_b = make_person("Bobby", "_Test Bounds Child", church=cls.branch_b).name
		cls.addClassCleanup(frappe.clear_cache)

	@classmethod
	def bind_volunteer(cls, email, first_name, church):
		user = ensure_user(email, first_name, roles=("Church Check-In",))
		make_person(first_name, "Volunteer", church=church, user=user)
		return user

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_the_station_gets_the_problem_of_each_person_outside_the_bounds(self):
		frappe.set_user(self.volunteer_a)
		problems = get_bound_problems(self.function.name, [self.child_a])
		self.assertEqual(list(problems), [self.child_a])
		self.assertEqual(problems[self.child_a]["full_name"], "Abby _Test Bounds Child")
		self.assertIn("No birth date", problems[self.child_a]["problem"])

	def test_only_the_functions_church_may_ask(self):
		frappe.set_user(self.volunteer_b)
		self.assertRaises(frappe.PermissionError, get_bound_problems, self.function.name, [self.child_b])

	def test_with_private_people_another_churchs_person_is_refused_unless_the_function_is_shared(self):
		set_private_people(True)
		self.addCleanup(set_private_people, False)
		joint = make_function("_Test Bounds Joint", church=self.branch_a, is_shared=1, max_age=10).name

		frappe.set_user(self.volunteer_a)
		self.assertRaises(frappe.PermissionError, get_bound_problems, self.function.name, [self.child_b])
		self.assertEqual(list(get_bound_problems(joint, [self.child_b])), [self.child_b])

	def test_only_a_reader_of_the_function_gets_its_rooms(self):
		frappe.set_user(self.volunteer_b)
		self.assertRaises(frappe.PermissionError, get_rooms, self.function.name)

		frappe.set_user(self.volunteer_a)
		self.assertEqual(get_rooms(self.function.name), [])


class TestCapacity(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.function = make_function("_Test Capacity Class", start_date=today())
		self.requester = make_person("Booker", "_Test Capacity").name
		self.book(self.room("_Test Capacity Room", 2))
		self.children = [make_person(f"Kid{index}", "_Test Capacity").name for index in range(4)]
		mode = frappe.get_cached_doc("Check-In Settings").capacity_mode
		self.addCleanup(frappe.db.set_single_value, "Check-In Settings", "capacity_mode", mode)

	def room(self, name, capacity, **values):
		return ensure(
			"Room",
			{"room_name": name},
			{"room_name": name, "capacity": capacity, "is_bookable": 1, **values},
		)

	def book(self, room, status="Approved"):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"requester": self.requester,
				"purpose": "_Test capacity",
				"start_datetime": f"{today()} 09:00:00",
				"end_datetime": f"{today()} 10:00:00",
				"function": self.function.name,
				"status": status,
			}
		).insert(ignore_permissions=True)

	def use_capacity_mode(self, mode):
		frappe.db.set_single_value("Check-In Settings", "capacity_mode", mode)

	def collect(self, check_in):
		frappe.db.set_value("Function Check-In", check_in, "collected_at", now_datetime())

	def test_the_station_names_the_approved_rooms(self):
		self.book(self.room("_Test Capacity Annex", 3))
		self.book(self.room("_Test Capacity Hall", 50, requires_approval=1), status="Requested")

		self.assertEqual(get_rooms(self.function.name), ["_Test Capacity Annex", "_Test Capacity Room"])

	def test_capacity_sums_the_approved_rooms_and_present_leaves_out_volunteers_and_collected(self):
		self.book(self.room("_Test Capacity Annex", 3))
		self.book(self.room("_Test Capacity Hall", 50, requires_approval=1), status="Requested")
		first, _second = add_check_ins(self.function.name, self.children[:2])
		add_check_ins(self.function.name, [self.children[2]], "Volunteer")
		self.collect(first)

		self.assertEqual(get_capacity(self.function.name), (1, 5))

	def test_block_refuses_a_full_room_until_a_child_is_collected(self):
		self.use_capacity_mode("Block")
		first, _second = add_check_ins(self.function.name, self.children[:2])

		self.assertRaises(RoomFullError, add_check_ins, self.function.name, [self.children[2]])
		self.assertFalse(frappe.db.exists("Function Check-In", {"person": self.children[2]}))

		self.collect(first)
		add_check_ins(self.function.name, [self.children[2]])
		self.assertTrue(frappe.db.exists("Function Check-In", {"person": self.children[2]}))

	def test_block_refuses_a_group_that_would_overfill_the_room(self):
		self.use_capacity_mode("Block")
		self.assertRaises(RoomFullError, add_check_ins, self.function.name, self.children[:3])

	def test_block_lets_a_volunteer_in_and_a_present_child_again(self):
		self.use_capacity_mode("Block")
		add_check_ins(self.function.name, self.children[:2])

		add_check_ins(self.function.name, [self.children[3]], "Volunteer")
		add_check_ins(self.function.name, self.children[:2])

		self.assertEqual(get_capacity(self.function.name), (2, 2))

	def test_block_refuses_a_check_in_made_on_the_form_and_no_kind_change_frees_a_place(self):
		self.use_capacity_mode("Block")
		first, _second = add_check_ins(self.function.name, self.children[:2])
		form = {"doctype": "Function Check-In", "function": self.function.name, "person": self.children[2]}

		self.assertRaises(RoomFullError, frappe.get_doc(form).insert)
		with self.assertRaises(frappe.CannotChangeConstantError):
			frappe.client.set_value("Function Check-In", first, "check_in_kind", "Volunteer")

		frappe.get_doc({**form, "check_in_kind": "Volunteer"}).insert()
		self.collect(first)
		frappe.get_doc({**form, "person": self.children[3]}).insert()
		self.assertEqual(get_capacity(self.function.name), (2, 2))

	def test_warn_saves_the_check_in_and_the_station_shows_a_warning(self):
		self.use_capacity_mode("Warn")
		self.assertNotIn("capacity_warning", check_in(self.function.name, self.children[:2]))

		result = check_in(self.function.name, [self.children[2]])

		self.assertEqual(len(result["check_ins"]), 1)
		self.assertIn("3", result["capacity_warning"])

	def test_off_neither_refuses_nor_warns(self):
		self.use_capacity_mode("Off")
		result = check_in(self.function.name, self.children[:3])

		self.assertEqual(len(result["check_ins"]), 3)
		self.assertNotIn("capacity_warning", result)

	def test_a_function_with_no_approved_booking_or_no_room_capacity_has_no_limit(self):
		self.use_capacity_mode("Block")
		unbooked = make_function("_Test Capacity Unbooked", start_date=today())
		self.assertEqual(get_capacity(unbooked.name), (0, 0))
		add_check_ins(unbooked.name, self.children[:3])

		self.function = make_function("_Test Capacity Unsized", start_date=today())
		self.book(self.room("_Test Capacity Unsized Room", 0))
		add_check_ins(self.function.name, self.children[:3])
		self.assertEqual(get_capacity(self.function.name), (3, 0))
