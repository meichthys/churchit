# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import email
import json
from pathlib import Path
from unittest.mock import PropertyMock, patch

import frappe
from frappe.utils import fmt_money, get_url

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	create_communication_purposes,
)
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CONFIRMATION_TEMPLATE,
	CONFIRMED,
	PENDING,
	REMINDER_TEMPLATE,
	UNPAID,
	WAITLISTED,
	FunctionSignUp,
	send_reminder,
)
from churchit.church_ministries.doctype.function_sign_up.test_sign_up_seats import make_sign_up
from churchit.ics import calendar_times
from churchit.patches.v1_0 import (
	add_sign_up_confirmation_template,
	add_sign_up_reminder_template,
	link_sign_up_and_welcome_emails,
	word_sign_up_link_as_see_your_sign_up,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	pop_logs,
)

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


def html_of(message) -> str:
	"""The decoded text of the one text/html part of *message*."""
	parts = [part for part in message.walk() if part.get_content_type() == "text/html"]
	assert len(parts) == 1, parts
	return parts[0].get_payload(decode=True).decode()


def shipped(folder: str) -> dict:
	"""The Email Template the app ships in the JSON of *folder*."""
	root = Path(frappe.get_app_path("churchit", "church_communications", "email_template", folder))
	return json.loads((root / f"{folder}.json").read_text())


def shipped_html(folder: str) -> str:
	return shipped(folder)["response_html"]


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
		cls.member_user = ensure_user("_test_confirmed_member@example.com", "_Test Member")
		cls.member = make_person(
			"_Test Portal",
			"Member",
			user=cls.member_user,
			emails=[{"email_address": "_test_confirmed_member@example.com", "is_primary": 1}],
		).name

	def setUp(self):
		super().setUp()
		# The person-linking, follow-up and promotion jobs are not what these tests are about.
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)
		# A site may hold an older copy of the template, which the patch would update.
		html = shipped_html("sign_up_confirmation_template")
		frappe.db.set_value("Email Template", CONFIRMATION_TEMPLATE, "response_html", html)

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
		self.assertTrue(pop_logs("Error Log", {"reference_name": sign_up.name}))

	def test_a_church_that_deletes_the_template_sends_no_confirmation(self):
		frappe.delete_doc("Email Template", CONFIRMATION_TEMPLATE, ignore_permissions=True)
		sign_up = make_sign_up(self.make_function().name, self.person, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(queued(sign_up), [])

	def test_a_sign_up_with_no_email_on_file_sends_nothing(self):
		sign_up = make_sign_up(self.make_function().name, self.other, attending=1)

		self.assertEqual(sign_up.status, CONFIRMED)
		self.assertEqual(queued(sign_up), [])

	def sign_up_as_member(self, function: str):
		"""A sign-up the member makes for themselves, as on /register."""
		frappe.set_user(self.member_user)
		try:
			return frappe.get_doc({"doctype": SIGN_UP, "function": function, "attending": 1}).insert(
				ignore_permissions=True
			)
		finally:
			frappe.set_user("Administrator")

	def test_an_amount_to_pay_at_the_church_is_named(self):
		fund = ensure("Fund", {"fund": "_Test Confirmation Fund"})
		adult = [{"selection": "Adult", "price": 20}]
		function = self.make_function(sign_up_fund=fund, selections=adult)
		offline = patch.object(
			FunctionSignUp, "has_online_payment", new_callable=PropertyMock, return_value=False
		)
		with offline:
			sign_up = make_sign_up(
				function.name, self.person, attendees=[{"person": self.person, "selection": "Adult"}]
			)

		self.assertEqual((sign_up.status, sign_up.payment_status), (CONFIRMED, UNPAID))
		[(_recipients, message)] = queued(sign_up)
		currency = frappe.get_cached_doc("Giving Settings").currency or "USD"
		amount = fmt_money(20, currency=currency)
		self.assertIn(f"The amount due is {amount}. Please pay it at the church.", html_of(message))

	def test_a_members_sign_up_links_to_its_page_whoever_made_it(self):
		own = self.sign_up_as_member(self.make_function().name)

		[(_recipients, message)] = queued(own)
		html = html_of(message)
		self.assertIn(f'<a href="{get_url(f"/function-sign-up/{own.name}")}"', html)
		self.assertIn("See your sign-up</a>", html)
		self.assertNotIn("amount due", html)

		by_staff = make_sign_up(self.make_function(start_date="2031-06-01").name, self.member, attending=1)
		[(_recipients, message)] = queued(by_staff)
		self.assertIn(get_url(f"/function-sign-up/{by_staff.name}"), html_of(message))

	def test_a_sign_up_whose_person_has_no_login_gets_no_link(self):
		sign_up = make_sign_up(self.make_function().name, self.person, attending=1)

		[(_recipients, message)] = queued(sign_up)
		self.assertNotIn("/function-sign-up/", html_of(message))

	def test_the_reminder_links_a_members_own_sign_up(self):
		create_communication_purposes()
		add_sign_up_reminder_template.execute()
		html = shipped_html("sign_up_reminder_template")
		frappe.db.set_value("Email Template", REMINDER_TEMPLATE, "response_html", html)
		own = self.sign_up_as_member(self.make_function().name)
		context = {"function_name": "_Test Confirmation Retreat", "date": "Thursday, May 1, 2031", "time": ""}

		with patch("frappe.sendmail") as sendmail, patch.object(frappe.db, "commit"):
			send_reminder(own, [EMAIL], context)

		[call] = sendmail.call_args_list
		link = get_url(f"/function-sign-up/{own.name}")
		self.assertIn(f'<a href="{link}">See your sign-up</a>', call.kwargs["message"])


class TestLinkSignUpAndWelcomeEmailsPatch(RollbackEachTest):
	def restore_shipped_text(self):
		for folder, html in link_sign_up_and_welcome_emails.SHIPPED.items():
			values = shipped(folder)
			if frappe.db.exists("Email Template", values["name"]):
				frappe.db.set_value("Email Template", values["name"], "response_html", html)
			else:
				frappe.get_doc({**values, "response_html": html}).insert(ignore_permissions=True)

	def test_the_patch_replaces_the_shipped_text_and_runs_twice(self):
		self.restore_shipped_text()

		link_sign_up_and_welcome_emails.execute()
		link_sign_up_and_welcome_emails.execute()

		for folder in link_sign_up_and_welcome_emails.SHIPPED:
			values = shipped(folder)
			self.assertEqual(
				frappe.db.get_value("Email Template", values["name"], "response_html"),
				values["response_html"],
			)

	def test_the_patch_keeps_a_churchs_own_words(self):
		self.restore_shipped_text()
		frappe.db.set_value("Email Template", CONFIRMATION_TEMPLATE, "response_html", "<p>Ours</p>")

		link_sign_up_and_welcome_emails.execute()

		self.assertEqual(
			frappe.db.get_value("Email Template", CONFIRMATION_TEMPLATE, "response_html"), "<p>Ours</p>"
		)


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


class TestWordSignUpLinkPatch(RollbackEachTest):
	def restore_old_link(self):
		for folder in word_sign_up_link_as_see_your_sign_up.TEMPLATES:
			values = shipped(folder)
			old = values["response_html"].replace("See your sign-up", "See or cancel your sign-up")
			if frappe.db.exists("Email Template", values["name"]):
				frappe.db.set_value("Email Template", values["name"], "response_html", old)
			else:
				frappe.get_doc({**values, "response_html": old}).insert(ignore_permissions=True)

	def test_the_patch_rewords_the_shipped_text_and_runs_twice(self):
		self.restore_old_link()

		word_sign_up_link_as_see_your_sign_up.execute()
		word_sign_up_link_as_see_your_sign_up.execute()

		for folder in word_sign_up_link_as_see_your_sign_up.TEMPLATES:
			values = shipped(folder)
			html = frappe.db.get_value("Email Template", values["name"], "response_html")
			self.assertEqual(html, values["response_html"])
			self.assertNotIn("or cancel", html)

	def test_the_patch_keeps_a_churchs_own_words(self):
		self.restore_old_link()
		ours = "<p>See or cancel your sign-up here, friend.</p>"
		frappe.db.set_value("Email Template", CONFIRMATION_TEMPLATE, "response_html", ours)

		word_sign_up_link_as_see_your_sign_up.execute()

		self.assertEqual(frappe.db.get_value("Email Template", CONFIRMATION_TEMPLATE, "response_html"), ours)
