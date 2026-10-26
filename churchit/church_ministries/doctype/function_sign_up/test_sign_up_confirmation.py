# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import email
from unittest.mock import patch

import frappe

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CONFIRMATION_TEMPLATE,
	CONFIRMED,
	PENDING,
	WAITLISTED,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.ics import calendar_times
from churchit.patches.v1_0 import add_sign_up_confirmation_template
from churchit.tests.helpers import RollbackEachTest, ensure, make_function, make_person

SIGN_UP = "Function Sign-Up"
CAN_SEND_EMAIL = "churchit.church_ministries.doctype.function_sign_up.function_sign_up.can_send_email"


def queued(sign_up) -> list:
	"""The emails queued for *sign_up*: each as (recipients, parsed MIME message)."""
	rows = frappe.get_all(
		"Email Queue", filters={"reference_doctype": SIGN_UP, "reference_name": sign_up.name}, pluck="name"
	)
	emails = []
	for name in rows:
		queue = frappe.get_doc("Email Queue", name)
		emails.append(([row.recipient for row in queue.recipients], email.message_from_string(queue.message)))
	return emails


def calendar_of(message) -> str:
	"""The text of the one text/calendar part of *message*, unfolded."""
	parts = [part for part in message.walk() if part.get_content_type() == "text/calendar"]
	assert len(parts) == 1, parts
	return parts[0].get_payload(decode=True).decode().replace("\r\n ", "")


class TestSignUpConfirmation(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Sign-Up Outgoing",
				"email_id": "_test_sign_up_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		add_sign_up_confirmation_template.execute()
		cls.person = make_person(
			"_Test Confirmed",
			"Member",
			emails=[{"email_address": "_test_confirmed@example.com", "is_primary": 1}],
		).name
		cls.other = make_person("_Test Waiting", "Member").name

	def setUp(self):
		super().setUp()
		# The person-linking, follow-up and promotion jobs are not what these tests are about.
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)

	def make_function(self, **values):
		times = {"start_date": "2031-05-01", "start_time": "18:30:00", "end_time": "20:00:00"}
		return make_function("_Test Confirmation Retreat", allow_sign_ups=1, **{**times, **values})

	def test_a_confirmed_sign_up_queues_one_email_with_the_event(self):
		function = self.make_function()
		sign_up = make_sign_up(function.name, self.person, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		[(recipients, message)] = queued(sign_up)
		self.assertEqual(recipients, ["_test_confirmed@example.com"])
		self.assertIn("_Test Confirmation Retreat", message["Subject"])
		calendar = calendar_of(message)
		self.assertIn(calendar_times(function)[0], calendar.split("\r\n"))
		self.assertIn("SUMMARY:_Test Confirmation Retreat", calendar)

	def test_an_all_day_function_gives_a_whole_day_event(self):
		function = self.make_function(all_day=1)
		[(_recipients, message)] = queued(make_sign_up(function.name, self.person, attending=1))

		self.assertIn("DTSTART;VALUE=DATE:20310501", calendar_of(message).split("\r\n"))

	def test_a_guest_sign_up_is_emailed_at_its_email(self):
		function = self.make_function()
		sign_up = make_sign_up(
			function.name, registrant_name="Gail _Test Guest", email="_test_gail@example.com", attending=1
		)

		self.assertFalse(sign_up.person)
		[(recipients, message)] = queued(sign_up)
		self.assertEqual(recipients, ["_test_gail@example.com"])
		self.assertIn("Dear Gail,", message.as_string())

	def test_a_sign_up_with_a_person_is_emailed_only_at_the_persons_own_email(self):
		function = self.make_function()
		typed = {"registrant_name": "Bob _Test Typed", "email": "_test_typed@example.com", "attending": 1}

		[(recipients, message)] = queued(make_sign_up(function.name, self.person, **typed))
		self.assertEqual(recipients, ["_test_confirmed@example.com"])
		self.assertIn("Dear _Test Confirmed,", message.as_string())
		self.assertEqual(queued(make_sign_up(function.name, self.other, **typed)), [])

	def test_saving_a_confirmed_sign_up_again_sends_no_second_email(self):
		sign_up = make_sign_up(self.make_function().name, self.person, attending=1)
		sign_up.notes = "_Test changed"
		sign_up.save(ignore_permissions=True)

		self.assertEqual(len(queued(sign_up)), 1)

	def test_a_sign_up_moved_to_another_function_is_confirmed_for_the_new_event(self):
		sign_up = make_sign_up(self.make_function().name, self.person, attending=1)
		later = self.make_function(start_date="2031-06-01")
		sign_up.function = later.name
		sign_up.save(ignore_permissions=True)

		calendars = [calendar_of(message) for _recipients, message in queued(sign_up)]
		self.assertEqual(len(calendars), 2)
		self.assertTrue(any(calendar_times(later)[0] in calendar.split("\r\n") for calendar in calendars))

	def test_a_pending_sign_up_is_confirmed_by_email_only_once_it_is_approved(self):
		sign_up = make_sign_up(self.make_function(sign_up_requires_approval=1).name, self.person, attending=1)
		self.assertEqual(sign_up.status, PENDING)
		self.assertEqual(queued(sign_up), [])

		sign_up.approve()

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(len(queued(sign_up)), 1)

	def test_a_waitlisted_sign_up_is_confirmed_by_email_only_once_it_is_promoted(self):
		function = self.make_function(capacity=1)
		first = make_sign_up(function.name, self.other, attending=1)
		waiting = make_sign_up(function.name, self.person, attending=1)
		self.assertEqual(waiting.status, WAITLISTED)
		self.assertEqual(queued(waiting), [])

		first.cancel_registration()

		self.assertEqual(frappe.db.get_value(SIGN_UP, waiting.name, "status"), CONFIRMED)
		self.assertEqual(len(queued(waiting)), 1)

	def test_with_no_outgoing_email_account_the_sign_up_still_saves(self):
		with patch(CAN_SEND_EMAIL, return_value=False):
			sign_up = make_sign_up(self.make_function().name, self.person, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(queued(sign_up), [])

	def test_a_mail_failure_is_logged_and_keeps_the_sign_up(self):
		with patch("frappe.sendmail", side_effect=OSError("_Test mail down")):
			sign_up = make_sign_up(self.make_function().name, self.person, attending=1)

		self.assertTrue(frappe.db.exists(SIGN_UP, {"name": sign_up.name, "status": CONFIRMED}))
		self.assertTrue(frappe.db.exists("Error Log", {"reference_name": sign_up.name}))

	def test_a_church_that_deletes_the_template_sends_no_confirmation(self):
		frappe.delete_doc("Email Template", CONFIRMATION_TEMPLATE, ignore_permissions=True)
		sign_up = make_sign_up(self.make_function().name, self.person, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(queued(sign_up), [])

	def test_a_sign_up_with_no_email_on_file_sends_nothing(self):
		sign_up = make_sign_up(self.make_function().name, self.other, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(queued(sign_up), [])


class TestSignUpConfirmationTemplatePatch(RollbackEachTest):
	def test_the_patch_adds_the_template_once_and_keeps_a_churchs_own_copy(self):
		frappe.db.delete("Email Template", {"name": CONFIRMATION_TEMPLATE})
		add_sign_up_confirmation_template.execute()
		self.assertTrue(frappe.db.get_value("Email Template", CONFIRMATION_TEMPLATE, "use_html"))

		frappe.db.set_value("Email Template", CONFIRMATION_TEMPLATE, "subject", "_Test our own subject")
		add_sign_up_confirmation_template.execute()

		self.assertEqual(
			frappe.db.get_value("Email Template", CONFIRMATION_TEMPLATE, "subject"), "_Test our own subject"
		)
