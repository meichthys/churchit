# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.utils import add_days, getdate, now_datetime

from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	get_team_emails,
	is_due_for_a_reminder,
	send_team_emails,
	send_team_emails_now,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
	make_two_churches,
)

MODULE = "churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment"


class TestMinistryTeamAssignment(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.alice = make_person(
			"_Test Team", "Alice", emails=[{"email_address": "_test_team_alice@example.com"}]
		)
		cls.bob = make_person("_Test Team", "Bob")
		cls.greeter = make_team_position("_Test Greeter", [cls.alice.name, cls.bob.name])
		cls.sunday = make_function(
			"_Test Team Sunday", start_date=add_days(getdate(), 7), start_time="10:00:00", end_time="11:00:00"
		)

	def setUp(self):
		super().setUp()
		self.sendmail = self.start(mock.patch("frappe.sendmail"))
		self.start(mock.patch(f"{MODULE}.can_send_email", return_value=True))

	def start(self, patcher):
		self.addCleanup(patcher.stop)
		return patcher.start()

	def sent_to(self, assignment):
		return [
			recipient
			for call in self.sendmail.call_args_list
			if call.kwargs["reference_name"] == assignment.name
			for recipient in call.kwargs["recipients"]
		]

	def new_assignment(self, person=None, function=None, position=None):
		return frappe.get_doc(
			{
				"doctype": "Ministry Team Assignment",
				"function": function or self.sunday.name,
				"position": position or self.greeter.name,
				"person": person or self.alice.name,
			}
		)

	def test_a_new_assignment_is_pending_with_its_own_response_key(self):
		first = make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		second = make_team_assignment(self.sunday.name, self.greeter.name, self.bob.name)

		self.assertEqual(first.status, "Pending")
		self.assertEqual(len(first.response_key), 32)
		self.assertNotEqual(first.response_key, second.response_key)
		self.assertEqual(first.title, f"_Test Team Alice as _Test Greeter at {self.sunday.title}")

	def test_only_the_people_listed_on_the_position_can_be_assigned(self):
		outsider = make_person("_Test Team", "Outsider")
		with self.assertRaisesRegex(frappe.ValidationError, "Add them to the position first"):
			self.new_assignment(person=outsider.name).insert(ignore_permissions=True)

	def test_the_same_person_cannot_be_assigned_twice_to_one_position_at_one_function(self):
		make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		with self.assertRaisesRegex(frappe.ValidationError, "already assigned"):
			self.new_assignment().insert(ignore_permissions=True)

	def test_warns_about_a_block_covering_the_function(self):
		frappe.get_doc(
			{
				"doctype": "Ministry Team Block",
				"person": self.alice.name,
				"from_date": self.sunday.start_date,
				"to_date": self.sunday.start_date,
				"reason": "Away",
			}
		).insert(ignore_permissions=True)

		warnings = self.new_assignment().get_warnings()
		self.assertTrue(any("Ministry Team Block" in warning and "Away" in warning for warning in warnings))

	def test_warns_when_the_person_already_serves_at_the_same_time(self):
		usher = make_team_position("_Test Usher", [self.alice.name])
		overlapping = make_function(
			"_Test Team Overlap",
			start_date=self.sunday.start_date,
			start_time="10:30:00",
			end_time="12:00:00",
		)
		after = make_function(
			"_Test Team After", start_date=self.sunday.start_date, start_time="12:00:00", end_time="13:00:00"
		)
		make_team_assignment(overlapping.name, usher.name, self.alice.name)

		self.assertTrue(any("same time" in warning for warning in self.new_assignment().get_warnings()))
		self.assertFalse(
			any(
				"same time" in warning for warning in self.new_assignment(function=after.name).get_warnings()
			),
			"a function that starts as the other ends does not overlap it",
		)

	def test_warns_when_a_position_needs_a_background_check_the_person_lacks(self):
		nursery = make_team_position("_Test Nursery", [self.alice.name], needs_background_check=1)
		self.assertTrue(
			any("Background Check" in w for w in self.new_assignment(position=nursery.name).get_warnings())
		)

		check_type = ensure("Background Check Type", {"type": "_Test Team Check"})
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": self.alice.name,
				"check_type": check_type,
				"status": "Cleared",
				"completed_on": getdate(),
				"expires_on": add_days(getdate(), 365),
			}
		).insert(ignore_permissions=True)
		self.assertFalse(
			any("Background Check" in w for w in self.new_assignment(position=nursery.name).get_warnings())
		)

	def clear(self, person, check_type, expires_on):
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": person,
				"check_type": ensure("Background Check Type", {"type": check_type}),
				"status": "Cleared",
				"completed_on": getdate(),
				"expires_on": expires_on,
			}
		).insert(ignore_permissions=True)

	def nursery(self, **values):
		"""A position needing a criminal check and child safety training."""
		required = [
			{"check_type": ensure("Background Check Type", {"type": check_type})}
			for check_type in ("_Test Criminal Check", "_Test Safety Training")
		]
		return make_team_position(
			"_Test Nursery", [self.alice.name], needs_background_check=1, required_checks=required, **values
		)

	def test_each_required_check_must_be_cleared(self):
		nursery = self.nursery()
		self.clear(self.alice.name, "_Test Criminal Check", add_days(getdate(), 365))

		warnings = self.new_assignment(position=nursery.name).get_warnings()
		self.assertTrue(any("is missing _Test Safety Training" in w for w in warnings), warnings)

		self.clear(self.alice.name, "_Test Safety Training", add_days(getdate(), 365))
		self.assertFalse(
			any("missing" in w for w in self.new_assignment(position=nursery.name).get_warnings())
		)

	def test_a_check_must_still_be_current_on_the_day_of_the_function(self):
		nursery = self.nursery()
		self.clear(self.alice.name, "_Test Criminal Check", add_days(getdate(), 365))
		self.clear(self.alice.name, "_Test Safety Training", add_days(self.sunday.start_date, -1))

		warnings = self.new_assignment(position=nursery.name).get_warnings()
		self.assertTrue(any("is missing _Test Safety Training" in w for w in warnings), warnings)

	def test_a_blocking_position_refuses_someone_without_the_checks(self):
		nursery = self.nursery(block_without_checks=1)
		self.clear(self.alice.name, "_Test Criminal Check", add_days(getdate(), 365))

		with self.assertRaisesRegex(frappe.ValidationError, "is missing _Test Safety Training"):
			self.new_assignment(position=nursery.name).insert(ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Ministry Team Assignment", {"position": nursery.name}))

		self.clear(self.alice.name, "_Test Safety Training", add_days(getdate(), 365))
		self.new_assignment(position=nursery.name).insert(ignore_permissions=True)

	def test_warns_when_the_person_has_no_email_address(self):
		self.assertTrue(
			any("no email address" in w for w in self.new_assignment(person=self.bob.name).get_warnings())
		)
		self.assertFalse(any("no email address" in w for w in self.new_assignment().get_warnings()))

	def test_an_answer_is_recorded_until_the_function_starts(self):
		assignment = make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		assignment.respond("Declined", "Out of town")
		assignment.save(ignore_permissions=True)

		self.assertEqual(assignment.decline_reason, "Out of town")
		self.assertIsNotNone(assignment.responded_on)

		assignment.respond("Accepted", "ignored")
		self.assertIsNone(assignment.decline_reason)
		with self.assertRaises(frappe.ValidationError):
			assignment.respond("Pending")

		frappe.db.set_value("Function", self.sunday.name, "start_date", add_days(getdate(), -1))
		frappe.clear_document_cache("Function", self.sunday.name)
		with self.assertRaisesRegex(frappe.ValidationError, "already started"):
			assignment.respond("Declined")

	def test_a_decline_emails_the_ministry_coordinator(self):
		coordinator = make_person(
			"_Test Team", "Coordinator", emails=[{"email_address": "_test_team_coordinator@example.com"}]
		)
		frappe.db.set_value("Ministry", self.greeter.ministry, "team_coordinator", coordinator.name)
		assignment = make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)

		assignment.respond("Declined", "Out of town")
		assignment.save(ignore_permissions=True)

		self.assertIn("_test_team_coordinator@example.com", self.sent_to(assignment))
		self.assertIn("Out of town", self.sendmail.call_args.kwargs["message"])

	def test_requests_go_out_once_in_one_email_per_person(self):
		second_sunday = make_function("_Test Team Next Sunday", start_date=add_days(getdate(), 14))
		first = make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		second = make_team_assignment(second_sunday.name, self.greeter.name, self.alice.name)
		no_email = make_team_assignment(self.sunday.name, self.greeter.name, self.bob.name)

		send_team_emails()
		send_team_emails()

		self.assertEqual(self.sent_to(first), ["_test_team_alice@example.com"])
		message = self.sendmail.call_args.kwargs["message"]
		self.assertIn(f"/ministry-team-response?key={first.response_key}", message)
		self.assertIn(f"/ministry-team-response?key={second.response_key}", message)
		self.assertIn("_Test Greeter", message)
		self.assertEqual(self.sent_to(second), [], "both requests share the first assignment's email")
		for assignment in (first, second, no_email):
			self.assertIsNotNone(
				frappe.db.get_value("Ministry Team Assignment", assignment.name, "requested_on")
			)

	def test_reminders_wait_for_the_ministrys_days_before(self):
		today = getdate()
		row = frappe._dict(
			status="Accepted",
			reminded_on=None,
			requested_on=add_days(now_datetime(), -3),
			team_reminder_days=2,
			start_date=add_days(today, 2),
		)
		self.assertTrue(is_due_for_a_reminder(row, today))
		self.assertFalse(is_due_for_a_reminder(frappe._dict(row, start_date=add_days(today, 3)), today))
		self.assertFalse(is_due_for_a_reminder(frappe._dict(row, team_reminder_days=0), today))
		self.assertFalse(is_due_for_a_reminder(frappe._dict(row, status="Declined"), today))
		self.assertFalse(is_due_for_a_reminder(frappe._dict(row, reminded_on=now_datetime()), today))
		self.assertFalse(
			is_due_for_a_reminder(frappe._dict(row, requested_on=now_datetime()), today),
			"a request sent today stands in for the reminder",
		)

	def test_the_daily_job_reminds_people_serving_soon(self):
		frappe.db.set_value("Ministry", self.greeter.ministry, "team_reminder_days", 7)
		assignment = make_team_assignment(
			self.sunday.name, self.greeter.name, self.alice.name, status="Accepted"
		)

		send_team_emails()

		self.assertEqual(self.sent_to(assignment), ["_test_team_alice@example.com"])
		self.assertIsNotNone(frappe.db.get_value("Ministry Team Assignment", assignment.name, "reminded_on"))

	def test_the_daily_job_waits_for_an_outgoing_email_account(self):
		assignment = make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		with mock.patch(f"{MODULE}.can_send_email", return_value=False):
			send_team_emails()
		self.assertIsNone(frappe.db.get_value("Ministry Team Assignment", assignment.name, "requested_on"))

	def test_send_emails_now_sends_what_the_daily_job_would_and_counts_it(self):
		make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		make_team_assignment(self.sunday.name, self.greeter.name, self.bob.name)

		self.assertEqual(send_team_emails_now(), 1, "Bob has no email address")
		self.assertEqual(send_team_emails_now(), 0)

	def test_send_emails_now_says_when_there_is_no_outgoing_email_account(self):
		with mock.patch(f"{MODULE}.can_send_email", return_value=False):
			with self.assertRaisesRegex(frappe.ValidationError, "outgoing Email Account"):
				send_team_emails_now()

	def test_send_emails_now_is_for_those_who_make_assignments(self):
		frappe.set_user(ensure_user("_test_team_member@example.com", "Member"))
		with self.assertRaises(frappe.PermissionError):
			send_team_emails_now()

	def test_email_the_team_reaches_everyone_asked_who_did_not_decline(self):
		usher = make_team_position("_Test Usher", [self.alice.name])
		make_team_assignment(self.sunday.name, self.greeter.name, self.alice.name)
		make_team_assignment(self.sunday.name, usher.name, self.alice.name)
		make_team_assignment(self.sunday.name, self.greeter.name, self.bob.name)
		carol = make_person("_Test Team", "Carol", emails=[{"email_address": "_test_team_carol@example.com"}])
		self.greeter.append("people", {"person": carol.name})
		self.greeter.save(ignore_permissions=True)
		make_team_assignment(self.sunday.name, self.greeter.name, carol.name, status="Declined")

		team = get_team_emails(self.sunday.name)

		self.assertEqual(team.emails, ["_test_team_alice@example.com"])
		self.assertEqual(team.without_email, ["_Test Team Bob"])

	def test_email_the_team_is_for_those_who_may_see_the_function(self):
		frappe.set_user(ensure_user("_test_team_member@example.com", "Member"))
		with self.assertRaises(frappe.PermissionError):
			get_team_emails(self.sunday.name)


class TestMinistryTeamAssignmentChurches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = ensure_user("_test_team_a@example.com", "Coordinator", roles=("Church Manager",))
		make_person("_Test Team", "Coordinator", church=cls.branch_a, user=cls.manager_a)
		server = make_person("_Test Team", "Server").name
		cls.teams = {}
		for key, church in (("A", cls.branch_a), ("B", cls.branch_b)):
			# The position is in the function's church, so only the user's access can refuse.
			ministry = f"_Test Team Ministry {key}"
			ensure("Ministry", {"ministry_name": ministry}, {"ministry_name": ministry, "church": church})
			cls.teams[key] = {
				"function": make_function(f"_Test Team {key}", church=church).name,
				"position": make_team_position(f"_Test Team {key}", [server], ministry_name=ministry).name,
				"person": server,
			}

	def test_only_the_functions_church_schedules_people_for_it(self):
		"""Frappe checks the create right before the assignment takes the function's church."""
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.PermissionError):
			frappe.new_doc("Ministry Team Assignment", **self.teams["B"]).insert()
		self.assertEqual(
			frappe.new_doc("Ministry Team Assignment", **self.teams["A"]).insert().church, self.branch_a
		)
