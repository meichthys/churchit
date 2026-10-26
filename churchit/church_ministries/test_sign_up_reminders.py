# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The registrant reminder (N5.2): sent through X1 with the Event Registrations purpose, once per channel."""

from unittest import mock

import frappe
from frappe.utils import add_days, format_date, today

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	EVENT_REGISTRATIONS,
	create_communication_purposes,
)
from churchit.church_communications.test_preferences import send_sms_hooks
from churchit.church_communications.test_sending import log_sms
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	PENDING,
	REMINDER_TEMPLATE,
	WAITLISTED,
	send_reminders,
)
from churchit.patches.v1_0 import add_event_registrations_purpose, add_sign_up_reminder_template
from churchit.tests.helpers import RollbackEachTest, force_single_church, make_function, make_person

SIGN_UP = "Function Sign-Up"
MODULE = "churchit.church_ministries.doctype.function_sign_up.function_sign_up"


def make_sign_up(function, person, status=None):
	sign_up = frappe.get_doc({"doctype": SIGN_UP, "function": function, "person": person}).insert()
	if status:
		frappe.db.set_value(SIGN_UP, sign_up.name, "status", status)
	return sign_up.name


class TestSignUpReminders(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		create_communication_purposes()
		add_sign_up_reminder_template.execute()

	def setUp(self):
		super().setUp()
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.can_send_email = mock.patch(f"{MODULE}.can_send_email", return_value=True).start()
		self.can_send_texts = mock.patch(f"{MODULE}.can_send_texts", return_value=False).start()
		mock.patch("frappe.db.commit").start()
		self.addCleanup(mock.patch.stopall)
		self.function = self.camp()
		self.people = [
			make_person(
				name,
				"_Test Reminder",
				emails=[{"email_address": f"_test_reminder_{name.lower()}@example.com"}],
				phones=[{"phone_number": f"555 010 02{index:02d}"}],
			).name
			for index, name in enumerate(("Ada", "Ben", "Cy", "Di", "Eve"))
		]

	def camp(self, days_ahead=2, reminder_days=3, **values):
		return make_function(
			"_Test Reminder Camp",
			start_date=add_days(today(), days_ahead),
			start_time="18:30:00",
			reminder_days=reminder_days,
			allow_sign_ups=1,
			**values,
		).name

	def reminded(self, key="reminder"):
		"""The people with a reminder copy of *key* about a sign-up, one entry per copy."""
		copies = frappe.get_all(
			"Communication",
			filters={"send_key": key, "reference_doctype": "Person"},
			fields=["name", "reference_name"],
		)
		linked = set(
			frappe.get_all(
				"Communication Link",
				filters={"link_doctype": SIGN_UP, "parent": ("in", [copy.name for copy in copies] or [""])},
				pluck="parent",
			)
		)
		return sorted(copy.reference_name for copy in copies if copy.name in linked)

	def test_running_twice_reminds_each_confirmed_registrant_once(self):
		ada, ben, cy, di, eve = self.people
		for person in (ada, ben):
			make_sign_up(self.function, person)
		make_sign_up(self.function, cy, CANCELLED)
		make_sign_up(self.function, di, PENDING)
		make_sign_up(self.function, eve, WAITLISTED)

		send_reminders()
		send_reminders()

		self.assertEqual(self.reminded(), sorted([ada, ben]))
		# The Sign-Up Confirmation goes to Ada too, with no unsubscribe link.
		[email] = [
			call.kwargs
			for call in self.sendmail.call_args_list
			if call.kwargs["recipients"] == ["_test_reminder_ada@example.com"]
			and call.kwargs.get("unsubscribe_params")
		]
		self.assertEqual(
			email["subject"], f"Reminder: _Test Reminder Camp on {format_date(add_days(today(), 2))}"
		)
		self.assertIn("Dear Ada", email["message"])
		self.assertIn("6:30 PM", email["message"])
		self.assertEqual(email["unsubscribe_params"]["purpose"], EVENT_REGISTRATIONS)

	def test_only_a_function_within_its_reminder_days_reminds(self):
		ada, ben, cy, di, _eve = self.people
		make_sign_up(self.function, ada)
		make_sign_up(self.camp(days_ahead=5), ben)
		make_sign_up(self.camp(days_ahead=1, reminder_days=0), cy)
		make_sign_up(self.camp(days_ahead=-1), di)

		send_reminders()

		self.assertEqual(self.reminded(), [ada])

	def test_a_registrant_who_withdrew_event_registrations_email_gets_none(self):
		ada, ben, *_others = self.people
		make_sign_up(self.function, ada)
		make_sign_up(self.function, ben)
		record([ada], EMAIL, WITHDRAWN, EVENT_REGISTRATIONS)

		send_reminders()

		self.assertEqual(self.reminded(), [ben])

	def test_only_a_registrant_who_gave_sms_consent_gets_the_text_once(self):
		ada, ben, *_others = self.people
		make_sign_up(self.function, ada)
		make_sign_up(self.function, ben)
		record([ada], SMS, GIVEN, EVENT_REGISTRATIONS)
		for patcher in (
			send_sms_hooks([]),
			mock.patch("churchit.church_communications.sending.send_sms", side_effect=log_sms),
		):
			patcher.start()

		send_reminders()
		self.assertEqual(self.reminded("reminder-text"), [])

		self.can_send_texts.return_value = True
		send_reminders()
		send_reminders()

		self.assertEqual(self.reminded("reminder-text"), [ada])
		self.assertEqual(self.reminded(), sorted([ada, ben]))

	def test_email_waits_for_an_outgoing_email_account(self):
		ada, *_others = self.people
		make_sign_up(self.function, ada)
		self.can_send_email.return_value = False

		send_reminders()
		self.assertEqual(self.reminded(), [])

		self.can_send_email.return_value = True
		send_reminders()
		self.assertEqual(self.reminded(), [ada])


class TestSignUpReminderSetup(RollbackEachTest):
	def test_the_purpose_patch_adds_event_registrations_once_and_it_cannot_be_deleted(self):
		frappe.db.delete("Communication Purpose", {"name": EVENT_REGISTRATIONS})

		add_event_registrations_purpose.execute()
		add_event_registrations_purpose.execute()

		self.assertEqual(frappe.db.count("Communication Purpose", {"name": EVENT_REGISTRATIONS}), 1)
		with self.assertRaisesRegex(frappe.ValidationError, "used by the app"):
			frappe.delete_doc("Communication Purpose", EVENT_REGISTRATIONS)

	def test_the_template_patch_adds_the_template_once_and_keeps_a_churchs_edits(self):
		frappe.db.delete("Email Template", {"name": REMINDER_TEMPLATE})

		add_sign_up_reminder_template.execute()
		self.assertIn(
			"{{ function_name }}", frappe.db.get_value("Email Template", REMINDER_TEMPLATE, "subject")
		)

		frappe.db.set_value("Email Template", REMINDER_TEMPLATE, "subject", "Ours")
		add_sign_up_reminder_template.execute()
		self.assertEqual(frappe.db.get_value("Email Template", REMINDER_TEMPLATE, "subject"), "Ours")
