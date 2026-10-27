# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest import mock

import frappe
from frappe.utils import add_days, getdate, today

from churchit.church_people import smart_lists, summaries
from churchit.church_people.summaries import refresh, serving
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)

NOTHING = {"last_served_on": None, "times_served_90d": 0}


def make_person_list(name, filters):
	"""A smart list: a saved Report Builder report on Person with *filters*."""
	return frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": "Person",
			"report_type": "Report Builder",
			"is_standard": "No",
			"json": json.dumps({"filters": filters}),
		}
	).insert(ignore_permissions=True)


def queued_people(save):
	"""The people each summary refresh queued by *save* names."""
	with mock.patch("frappe.enqueue") as enqueue:
		save()
	return [call.kwargs["people"] for call in enqueue.call_args_list if "people" in call.kwargs]


class TestServingSummary(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Server", "Summary").name
		self.position = make_team_position("_Test Serving Greeter", [self.person]).name

	def serve(self, days_from_today, status="Accepted"):
		start_date = add_days(today(), days_from_today)
		function = make_function(f"_Test Serving {days_from_today}", start_date=start_date)
		return make_team_assignment(function.name, self.position, self.person, status=status)

	def summary(self):
		refresh([self.person])
		return frappe.db.get_value("Person", self.person, list(NOTHING), as_dict=True)

	def test_last_served_and_the_functions_served_in_the_last_90_days(self):
		self.serve(-serving.WINDOW_DAYS - 1)
		self.serve(-serving.WINDOW_DAYS)
		self.serve(-2)

		summary = self.summary()

		self.assertEqual(summary.last_served_on, getdate(add_days(today(), -2)))
		self.assertEqual(summary.times_served_90d, 2)

	def test_two_positions_at_one_function_count_as_one_time(self):
		usher = make_team_position("_Test Serving Usher", [self.person]).name
		function = self.serve(-3).function
		make_team_assignment(function, usher, self.person, status="Accepted")

		self.assertEqual(self.summary().times_served_90d, 1)

	def test_only_an_accepted_assignment_counts(self):
		self.serve(-3, "Pending")
		self.serve(-2, "Declined")

		self.assertEqual(self.summary(), NOTHING)

	def test_a_function_still_to_come_does_not_count(self):
		self.serve(7)

		self.assertEqual(self.summary(), NOTHING)

	def test_answering_an_assignment_queues_its_person(self):
		assignment = self.serve(7, "Pending")
		assignment.respond("Accepted")

		self.assertEqual(queued_people(lambda: assignment.save(ignore_permissions=True)), [[self.person]])

	def test_an_assignment_queues_the_person_it_named_before_the_save(self):
		other = make_person("_Test Former", "Server").name
		assignment = self.serve(-2)
		assignment.load_doc_before_save()
		assignment.person = other

		self.assertEqual(
			queued_people(lambda: summaries.on_change(assignment, "on_update")),
			[sorted([self.person, other])],
		)

	def test_moving_a_function_moves_its_teams_serving_date(self):
		function = frappe.get_doc("Function", self.serve(-10).function)
		function.start_date = add_days(today(), -5)

		self.assertEqual(queued_people(lambda: function.save(ignore_permissions=True)), [[self.person]])
		self.assertEqual(self.summary().last_served_on, getdate(add_days(today(), -5)))


class TestTeamPositionsSummary(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.person = make_person("_Test Team", "Summary").name

	def teams(self):
		refresh([self.person])
		person = frappe.get_doc("Person", self.person)
		return [row.ministry for row in person.ministry_teams], [
			row.position for row in person.team_positions
		]

	def test_the_positions_that_list_a_person_and_their_ministries(self):
		greeter = make_team_position("_Test Team Greeter", [self.person], "_Test Team Welcome")
		usher = make_team_position("_Test Team Usher", [self.person], "_Test Team Welcome")
		singer = make_team_position("_Test Team Singer", [self.person], "_Test Team Choir")
		make_team_position("_Test Team Other", [], "_Test Team Choir")

		self.assertEqual(
			self.teams(),
			([singer.ministry, greeter.ministry], [singer.name, greeter.name, usher.name]),
		)

	def test_taking_a_person_off_a_position_queues_and_clears_it(self):
		position = make_team_position("_Test Team Leaving", [self.person])
		self.teams()
		position.people = []

		self.assertEqual(queued_people(lambda: position.save(ignore_permissions=True)), [[self.person]])
		self.assertEqual(self.teams(), ([], []))

	def test_an_inactive_ministry_is_left_out_and_its_status_change_queues_its_people(self):
		position = make_team_position("_Test Team Paused", [self.person], "_Test Team Paused Ministry")
		ministry = frappe.get_doc("Ministry", position.ministry)
		self.assertEqual(self.teams(), ([ministry.name], [position.name]))
		ministry.description = "Meets on Sundays"

		self.assertEqual(queued_people(lambda: ministry.save(ignore_permissions=True)), [])
		ministry.status = serving.INACTIVE
		self.assertEqual(queued_people(lambda: ministry.save(ignore_permissions=True)), [[self.person]])
		self.assertEqual(self.teams(), ([], []))

	def test_a_list_on_a_team_or_a_position_returns_the_people_it_lists(self):
		other = make_person("_Test Team Other", "Summary").name
		position = make_team_position("_Test Team Listed", [self.person], "_Test Team Listed Ministry")
		make_team_position("_Test Team Not Listed", [other])
		refresh([self.person, other])
		by_team = make_person_list(
			"_Test Team List", [["Person Ministry Team", "ministry", "=", position.ministry]]
		)
		by_position = make_person_list(
			"_Test Position List", [["Person Team Position", "position", "=", position.name]]
		)

		self.assertEqual(smart_lists.get_people(by_team.name, None), [self.person])
		self.assertEqual(smart_lists.get_people(by_position.name, None), [self.person])

	def test_a_position_that_lists_people_can_be_deleted(self):
		position = make_team_position("_Test Team Deleted", [self.person])
		self.teams()

		frappe.delete_doc("Ministry Team Position", position.name)

		self.assertEqual(self.teams(), ([], []))


class TestServingStaysInItsChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)

	def test_another_churchs_function_counts_only_once_it_is_shared(self):
		"""The assignment keeps the church it was made with, so the function's church is the one compared."""
		person = make_person("_Test Branch", "Server", church=self.branch_a).name
		ministry = {"ministry_name": "_Test Serving Branch B", "church": self.branch_b}
		ensure("Ministry", {"ministry_name": ministry["ministry_name"]}, ministry)
		position = make_team_position("_Test Serving Greeter", [person], ministry["ministry_name"]).name
		function = make_function(
			"_Test Serving Branch B", start_date=add_days(today(), -1), church=self.branch_b
		)
		make_team_assignment(function.name, position, person, status="Accepted")
		refresh([person])
		self.assertEqual(frappe.db.get_value("Person", person, "times_served_90d"), 0)

		function.is_shared = 1
		function.save(ignore_permissions=True)
		refresh([person])
		self.assertEqual(frappe.db.get_value("Person", person, "times_served_90d"), 1)

	def test_another_churchs_position_is_left_out(self):
		person = make_person("_Test Branch", "Team", church=self.branch_a).name
		mine = {"ministry_name": "_Test Team Branch A", "church": self.branch_a}
		ensure("Ministry", {"ministry_name": mine["ministry_name"]}, mine)
		theirs = {"ministry_name": "_Test Team Branch B", "church": self.branch_b}
		ensure("Ministry", {"ministry_name": theirs["ministry_name"]}, theirs)
		kept = make_team_position("_Test Team Kept", [person], mine["ministry_name"])
		make_team_position("_Test Team Left Out", [person], theirs["ministry_name"])
		refresh([person])

		self.assertEqual(
			frappe.get_all("Person Team Position", filters={"parent": person}, pluck="position"), [kept.name]
		)
		self.assertEqual(
			frappe.get_all("Person Ministry Team", filters={"parent": person}, pluck="ministry"),
			[kept.ministry],
		)
