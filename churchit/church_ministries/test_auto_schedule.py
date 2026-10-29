# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import threading
import time
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate

from churchit.church_ministries.auto_schedule import fill_open_needs, fill_open_needs_between
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)

SUNDAY = "2031-05-04"


def make_sunday(name, positions, quantity=1, **values):
	"""A future Sunday function from 10 to 11 that needs *quantity* people in each of *positions*."""
	return make_function(
		name,
		start_date=SUNDAY,
		start_time="10:00:00",
		end_time="11:00:00",
		team_needs=[{"position": position, "quantity": quantity} for position in positions],
		**values,
	)


def assigned_people(function, position=None):
	filters = {"function": function, "status": ("!=", "Declined")}
	if position:
		filters["position"] = position
	return set(frappe.get_all("Ministry Team Assignment", filters=filters, pluck="person"))


class TestFillOpenNeeds(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.people = {
			name: make_person(name, "_Test Fill").name
			for name in ("Blocked", "Weekly", "Booked", "Limited", "Deceased", "Free", "Spare")
		}
		cls.usher = make_team_position("_Test Fill Usher", list(cls.people.values()))
		cls.other = make_team_position("_Test Fill Other", list(cls.people.values()))

	def setUp(self):
		super().setUp()
		self.enterContext(mock.patch.object(frappe.db, "commit"))  # each fill commits before its lock

	def test_the_fill_never_picks_someone_who_cannot_serve(self):
		people = self.people
		sunday = make_sunday("_Test Fill Sunday", [self.usher.name], quantity=5)
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": people["Blocked"],
				"from_date": SUNDAY,
				"to_date": SUNDAY,
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": people["Weekly"],
				"from_date": "2031-04-20",
				"to_date": "2031-04-20",
				"repeat_frequency": "Weekly",
			}
		).insert(ignore_permissions=True)
		overlapping = make_function(
			"_Test Fill Overlap", start_date=SUNDAY, start_time="10:30:00", end_time="12:00:00"
		)
		make_team_assignment(overlapping.name, self.other.name, people["Booked"])
		self.set_limit(people["Limited"], 1)
		earlier = make_function("_Test Fill Earlier", start_date="2031-05-01")
		make_team_assignment(earlier.name, self.usher.name, people["Limited"], status="Accepted")
		frappe.db.set_value("Person", people["Deceased"], "is_deceased", 1)

		result = fill_open_needs(sunday.name)

		self.assertEqual(assigned_people(sunday.name), {people["Free"], people["Spare"]})
		self.assertEqual(
			[(row.position, row.open) for row in result.unfilled], [(self.usher.name, 3)], result
		)
		self.assertEqual({row.person for row in result.assigned}, {people["Free"], people["Spare"]})
		statuses = frappe.get_all(
			"Ministry Team Assignment", filters={"function": sunday.name}, pluck="status"
		)
		self.assertEqual(statuses, ["Pending", "Pending"])

	def test_the_fill_skips_people_without_the_checks_the_position_needs(self):
		check_type = ensure("Background Check Type", {"type": "_Test Fill Check"})
		nursery = make_team_position(
			"_Test Fill Nursery",
			[self.people["Free"], self.people["Spare"]],
			needs_background_check=1,
			required_checks=[{"check_type": check_type}],
		)
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": self.people["Spare"],
				"check_type": check_type,
				"status": "Cleared",
				"completed_on": getdate(),
				"expires_on": "2032-12-31",
			}
		).insert(ignore_permissions=True)
		sunday = make_sunday("_Test Fill Nursery Sunday", [nursery.name], quantity=2)

		result = fill_open_needs(sunday.name)

		self.assertEqual(assigned_people(sunday.name), {self.people["Spare"]})
		self.assertEqual([row.open for row in result.unfilled], [1])

	def test_a_second_run_creates_nothing(self):
		sunday = make_sunday("_Test Fill Twice", [self.usher.name], quantity=2)
		self.assertEqual(len(fill_open_needs(sunday.name).assigned), 2)

		result = fill_open_needs(sunday.name)

		self.assertEqual(result.assigned, [])
		self.assertEqual(result.unfilled, [])
		self.assertEqual(frappe.db.count("Ministry Team Assignment", {"function": sunday.name}), 2)

	def test_a_decline_reopens_the_place_for_someone_else(self):
		sunday = make_sunday("_Test Fill Decline", [self.usher.name])
		[first] = fill_open_needs(sunday.name).assigned
		declined = frappe.get_doc("Ministry Team Assignment", first.assignment)
		declined.respond("Declined", "Away")
		declined.save(ignore_permissions=True)

		[second] = fill_open_needs(sunday.name).assigned

		self.assertNotEqual(second.person, first.person)
		self.assertEqual(assigned_people(sunday.name), {second.person})

	def test_who_served_longest_ago_is_asked_first(self):
		for name, last_served_on in (("Free", "2031-04-27"), ("Spare", "2031-01-05")):
			frappe.db.set_value("Person", self.people[name], "last_served_on", last_served_on)
		for name in ("Blocked", "Weekly", "Booked", "Limited", "Deceased"):
			frappe.db.set_value("Person", self.people[name], "last_served_on", "2031-04-27")
		sunday = make_sunday("_Test Fill Rank", [self.usher.name])

		[assigned] = fill_open_needs(sunday.name).assigned

		self.assertEqual(assigned.person, self.people["Spare"])

	def test_a_person_fills_one_position_of_a_function(self):
		sunday = make_sunday("_Test Fill Two Positions", [self.usher.name, self.other.name], quantity=4)

		result = fill_open_needs(sunday.name)

		self.assertTrue(assigned_people(sunday.name, self.usher.name))
		self.assertFalse(
			assigned_people(sunday.name, self.usher.name) & assigned_people(sunday.name, self.other.name)
		)
		self.assertEqual(len(result.assigned), len(self.people))

	def test_a_range_fill_takes_the_functions_and_ministry_chosen(self):
		ministry = ensure("Ministry", {"ministry_name": "_Test Fill Music"})
		singer = make_team_position(
			"_Test Fill Singer", [self.people["Free"]], ministry_name="_Test Fill Music"
		)
		inside = make_sunday("_Test Fill Inside", [self.usher.name, singer.name])
		outside = make_function(
			"_Test Fill Outside",
			start_date="2031-06-01",
			team_needs=[{"position": singer.name, "quantity": 1}],
		)

		result = fill_open_needs_between("2031-05-01", "2031-05-31", ministry)

		self.assertEqual(
			[(row.function, row.position) for row in result.assigned], [(inside.name, singer.name)]
		)
		self.assertEqual(assigned_people(inside.name, self.usher.name), set())
		self.assertEqual(assigned_people(outside.name), set())

	def test_a_fill_of_one_function_takes_the_ministry_chosen(self):
		ministry = ensure("Ministry", {"ministry_name": "_Test Fill Music"})
		singer = make_team_position(
			"_Test Fill Singer", [self.people["Free"]], ministry_name="_Test Fill Music"
		)
		sunday = make_sunday("_Test Fill One Ministry", [self.usher.name, singer.name])

		result = fill_open_needs(sunday.name, ministry)

		self.assertEqual([row.position for row in result.assigned], [singer.name])
		self.assertEqual(assigned_people(sunday.name, self.usher.name), set())

	def test_a_function_that_started_is_not_filled(self):
		past = make_function(
			"_Test Fill Past",
			start_date=str(add_days(getdate(), -1)),
			team_needs=[{"position": self.usher.name, "quantity": 1}],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "has already started"):
			fill_open_needs(past.name)
		fill_open_needs_between(str(add_days(getdate(), -7)), SUNDAY, self.usher.ministry)
		self.assertEqual(assigned_people(past.name), set())

	def set_limit(self, person, limit):
		position = frappe.get_doc("Ministry Team Position", self.usher.name)
		for row in position.people:
			if row.person == person:
				row.max_times_per_month = limit
		position.save(ignore_permissions=True)


class TestFillOpenNeedsChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_fill_a@example.com", "Fill A", roles=("Church Manager",))
		cls.manager_b = ensure_user("_test_fill_b@example.com", "Fill B", roles=("Church Manager",))
		cls.member = ensure_user("_test_fill_member@example.com", "Fill Member", roles=("Church User",))
		cls.manager_all = ensure_user("_test_fill_all@example.com", "Fill All", roles=("Church Manager",))
		make_person("_Test Fill", "Manager A", church=cls.branch_a, user=cls.manager_a)
		make_person("_Test Fill", "Manager B", church=cls.branch_b, user=cls.manager_b)
		make_person("_Test Fill", "Member", church=cls.branch_a, user=cls.member)
		cls.positions = {}
		for key, church in (("A", cls.branch_a), ("B", cls.branch_b)):
			ministry = f"_Test Fill {key}"
			ensure("Ministry", {"ministry_name": ministry}, {"ministry_name": ministry, "church": church})
			server = make_person("_Test Fill", f"Server {key}", church=church).name
			cls.positions[key] = make_team_position(ministry, [server], ministry_name=ministry).name
		cls.function_a = make_sunday("_Test Fill A", [cls.positions["A"]], church=cls.branch_a).name
		cls.shared = make_sunday(
			"_Test Fill Shared", list(cls.positions.values()), church=cls.branch_a, is_shared=1
		).name

	def setUp(self):
		super().setUp()
		self.enterContext(mock.patch.object(frappe.db, "commit"))  # each fill commits before its lock

	def test_a_church_fills_only_its_own_functions_and_positions(self):
		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			fill_open_needs(self.function_a)
		result = fill_open_needs_between("2031-05-01", "2031-05-31")

		self.assertEqual(
			[(row.function, row.position) for row in result.assigned], [(self.shared, self.positions["B"])]
		)
		self.assertNotIn(self.function_a, [row.function for row in result.unfilled])

		frappe.set_user(self.manager_a)
		[assigned] = fill_open_needs(self.function_a).assigned
		self.assertEqual(
			frappe.db.get_value("Ministry Team Assignment", assigned.assignment, "church"), self.branch_a
		)

	def test_a_range_fill_takes_only_the_church_chosen(self):
		function_b = make_sunday("_Test Fill B", [self.positions["B"]], church=self.branch_b).name
		frappe.set_user(self.manager_b)
		with self.assertRaises(frappe.PermissionError):
			fill_open_needs_between("2031-05-01", "2031-05-31", church=self.branch_a)

		frappe.set_user("Administrator")
		for permission in frappe.get_all(
			"User Permission", filters={"user": self.manager_all, "allow": "Church"}, pluck="name"
		):
			frappe.delete_doc("User Permission", permission, ignore_permissions=True, force=True)
		self.addCleanup(frappe.clear_cache, user=self.manager_all)
		frappe.set_user(self.manager_all)
		result = fill_open_needs_between("2031-05-01", "2031-05-31", church=self.branch_a)

		self.assertEqual({row.function for row in result.assigned}, {self.function_a})
		frappe.set_user("Administrator")
		self.assertEqual(assigned_people(function_b), set())

	def test_a_user_who_cannot_create_assignments_fills_nothing(self):
		frappe.set_user(self.member)
		for call in (
			lambda: fill_open_needs(self.function_a),
			lambda: fill_open_needs_between("2031-05-01", "2031-05-31"),
		):
			with self.assertRaises(frappe.PermissionError):
				call()
		frappe.set_user("Administrator")
		self.assertEqual(assigned_people(self.function_a), set())

	def test_one_church_still_fills_its_functions(self):
		force_single_church()
		[assigned] = fill_open_needs(self.function_a).assigned
		self.assertEqual(assigned.position, self.positions["A"])


class TestFillRace(FrappeTestCase):
	"""Two fills of one function, each with its own connection. Commits real data, deleted at the end."""

	def test_a_second_fill_at_the_same_time_sees_the_first_fills_requests(self):
		people = [make_person("_Test Fill", f"Racer {number}").name for number in (1, 2)]
		position = make_team_position("_Test Fill Race Usher", people)
		sunday = make_sunday("_Test Fill Race", [position.name])
		frappe.db.commit()
		try:
			results = fill_at_once(sunday.name)
			self.assertEqual(len(results["first"]), 1, results)
			self.assertEqual(results["second"], [], results)
			self.assertEqual(frappe.db.count("Ministry Team Assignment", {"function": sunday.name}), 1)
		finally:
			frappe.db.rollback()
			for name in frappe.get_all("Ministry Team Assignment", {"function": sunday.name}, pluck="name"):
				frappe.delete_doc("Ministry Team Assignment", name, force=True, ignore_permissions=True)
			frappe.delete_doc("Function", sunday.name, force=True, ignore_permissions=True)
			frappe.delete_doc("Ministry Team Position", position.name, force=True, ignore_permissions=True)
			for person in people:
				frappe.delete_doc("Person", person, force=True, ignore_permissions=True)
			frappe.db.commit()

	def test_a_fill_of_another_function_at_the_same_time_does_not_double_book(self):
		person = make_person("_Test Fill", "Racer Both").name
		names = ("Usher", "Greeter")
		positions = [make_team_position(f"_Test Fill Race Both {name}", [person]) for name in names]
		sundays = [
			make_sunday(f"_Test Fill Race Both {name}", [position.name])
			for name, position in zip(names, positions, strict=True)
		]
		frappe.db.commit()
		try:
			results = fill_at_once(*(sunday.name for sunday in sundays))
			self.assertEqual((results["first"], results["second"]), ([person], []), results)
		finally:
			frappe.db.rollback()
			for name in frappe.get_all("Ministry Team Assignment", {"person": person}, pluck="name"):
				frappe.delete_doc("Ministry Team Assignment", name, force=True, ignore_permissions=True)
			for doc in (*sundays, *positions):
				frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
			frappe.delete_doc("Person", person, force=True, ignore_permissions=True)
			frappe.db.commit()


def fill_at_once(function: str, second_function: str | None = None) -> dict:
	"""Fill *function* in two threads, the second while the first has not committed. Returns who each asked.

	The second thread fills *second_function* when it is given.
	"""
	site, sites_path = frappe.local.site, frappe.local.sites_path
	filled, read = threading.Event(), threading.Event()
	results = {}

	def fill(key, function, before_fill, after_fill):
		frappe.init(site, sites_path=sites_path)
		frappe.connect()
		try:
			before_fill()
			results[key] = [row.person for row in fill_open_needs(function).assigned]
			after_fill()
			frappe.db.commit()
		except Exception as error:
			results[key] = error
		finally:
			filled.set()
			read.set()
			frappe.destroy()

	def take_a_snapshot():
		filled.wait(30)
		frappe.db.get_value("Function", function, "title")  # a plain read before the first fill commits
		read.set()

	def wait_for_the_second_fill():
		filled.set()
		read.wait(30)
		time.sleep(1)  # the second fill now waits for the Function lock

	threads = [
		threading.Thread(target=fill, args=("first", function, lambda: None, wait_for_the_second_fill)),
		threading.Thread(
			target=fill, args=("second", second_function or function, take_a_snapshot, lambda: None)
		),
	]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=60)
	return results
