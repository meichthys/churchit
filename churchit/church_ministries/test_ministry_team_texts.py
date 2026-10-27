# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Ministry team requests and reminders by text (N7.1): sent through X1 with the Serving purpose."""

from unittest import mock

import frappe
from frappe.utils import add_days, getdate

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	GIVEN,
	SMS,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import SERVING
from churchit.church_communications.test_preferences import send_sms_hooks, set_sms_gateway
from churchit.church_communications.test_sending import gateway_error, log_sms
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	send_team_emails,
	send_team_emails_now,
)
from churchit.patches.v1_0 import add_serving_purpose
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)

ASSIGNMENT = "Ministry Team Assignment"
MODULE = "churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment"


class TestMinistryTeamTexts(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		add_serving_purpose.execute()
		cls.ann, cls.ben = (
			make_person(
				"_Test Text Team",
				name,
				emails=[{"email_address": f"_test_text_team_{name.lower()}@example.com"}],
				phones=[{"phone_number": f"555 010 03{index:02d}"}],
			).name
			for index, name in enumerate(("Ann", "Ben"))
		)
		cls.position = make_team_position("_Test Text Greeter", [cls.ann, cls.ben])
		cls.sunday = make_function(
			"_Test Text Sunday", start_date=add_days(getdate(), 5), start_time="10:00:00", end_time="11:00:00"
		).name

	def setUp(self):
		super().setUp()
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.can_send_email = mock.patch(f"{MODULE}.can_send_email", return_value=True).start()
		mock.patch("frappe.db.commit").start()
		send_sms_hooks([]).start()
		self.send_sms = mock.patch("churchit.church_communications.sending.send_sms", side_effect=log_sms)
		self.send_sms.start()
		self.addCleanup(mock.patch.stopall)
		set_sms_gateway("https://sms.example.com/send")
		record([self.ann], SMS, GIVEN, SERVING)

	def emailed(self, assignment):
		return [
			recipient
			for call in self.sendmail.call_args_list
			if call.kwargs["reference_name"] == assignment.name
			for recipient in call.kwargs["recipients"]
		]

	def texts(self, assignment, key):
		"""The text copies of *key* about *assignment*, as the people they went to."""
		copies = frappe.get_all(
			"Communication",
			filters={"send_key": key, "communication_medium": "SMS", "reference_doctype": "Person"},
			fields=["name", "reference_name", "content"],
		)
		linked = set(
			frappe.get_all(
				"Communication Link",
				filters={
					"link_doctype": ASSIGNMENT,
					"link_name": assignment.name,
					"parent": ("in", [copy.name for copy in copies] or [""]),
				},
				pluck="parent",
			)
		)
		return [copy for copy in copies if copy.name in linked]

	def test_a_request_with_consent_goes_by_email_and_text_once(self):
		assignment = make_team_assignment(self.sunday, self.position.name, self.ann)

		self.assertEqual(send_team_emails(), 2)
		self.assertEqual(send_team_emails(), 0)

		self.assertEqual(self.emailed(assignment), ["_test_text_team_ann@example.com"])
		[text] = self.texts(assignment, "request")
		self.assertEqual(text.reference_name, self.ann)
		self.assertIn("_Test Text Greeter", text.content)
		self.assertIn(f"/ministry-team-response?key={assignment.response_key}", text.content)
		self.assertEqual(frappe.db.count("SMS Log", {"message": ("like", "%_Test Text Sunday%")}), 1)

	def test_a_reminder_with_consent_goes_by_email_and_text_once(self):
		frappe.db.set_value("Ministry", self.position.ministry, "team_reminder_days", 7)
		ann = make_team_assignment(self.sunday, self.position.name, self.ann, status="Accepted")
		ben = make_team_assignment(self.sunday, self.position.name, self.ben, status="Accepted")

		self.assertEqual(send_team_emails(), 3)
		self.assertEqual(send_team_emails(), 0)

		self.assertEqual(self.emailed(ann), ["_test_text_team_ann@example.com"])
		self.assertEqual(self.emailed(ben), ["_test_text_team_ben@example.com"])
		self.assertEqual([text.reference_name for text in self.texts(ann, "reminder")], [self.ann])
		self.assertEqual(self.texts(ben, "reminder"), [], "Ben gave no text consent for Serving")

	def test_a_request_without_consent_goes_only_by_email(self):
		assignment = make_team_assignment(self.sunday, self.position.name, self.ben)

		self.assertEqual(send_team_emails(), 1)

		self.assertEqual(self.emailed(assignment), ["_test_text_team_ben@example.com"])
		self.assertEqual(self.texts(assignment, "request"), [])
		self.assertIsNotNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "requested_on"))

	def test_with_a_gateway_and_no_email_account_the_request_text_still_goes(self):
		self.can_send_email.return_value = False
		assignment = make_team_assignment(self.sunday, self.position.name, self.ann)

		self.assertEqual(send_team_emails_now(), 1)

		self.sendmail.assert_not_called()
		self.assertEqual(len(self.texts(assignment, "request")), 1)
		self.assertIsNotNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "requested_on"))

	def test_without_a_gateway_or_an_email_account_nothing_is_marked_sent(self):
		self.can_send_email.return_value = False
		set_sms_gateway("")
		assignment = make_team_assignment(self.sunday, self.position.name, self.ann)

		self.assertEqual(send_team_emails(), 0)
		with self.assertRaisesRegex(frappe.ValidationError, "outgoing Email Account"):
			send_team_emails_now()

		self.assertIsNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "requested_on"))

	def test_without_a_gateway_only_the_email_goes(self):
		set_sms_gateway("")
		assignment = make_team_assignment(self.sunday, self.position.name, self.ann)

		self.assertEqual(send_team_emails(), 1)

		self.assertEqual(self.emailed(assignment), ["_test_text_team_ann@example.com"])
		self.assertEqual(self.texts(assignment, "request"), [])

	def test_a_gateway_failure_stops_the_texts_and_the_emails_still_go(self):
		frappe.db.set_value("Ministry", self.position.ministry, "team_reminder_days", 7)
		next_sunday = make_function("_Test Text Next Sunday", start_date=add_days(getdate(), 12)).name
		requests = [
			make_team_assignment(function, self.position.name, self.ann)
			for function in (self.sunday, next_sunday)
		]
		reminder = make_team_assignment(self.sunday, self.position.name, self.ben, status="Accepted")

		with mock.patch(
			"churchit.church_communications.sending.send_sms", side_effect=gateway_error(503)
		) as send_sms:
			self.assertEqual(send_team_emails(), 2, "Ann's request email and Ben's reminder email")

		self.assertEqual(send_sms.call_count, 1, "the first failure stops the texts")
		self.assertEqual(self.emailed(requests[0]), ["_test_text_team_ann@example.com"])
		self.assertEqual(self.emailed(reminder), ["_test_text_team_ben@example.com"])
		for assignment in requests:
			self.assertIsNotNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "requested_on"))
			self.assertEqual(self.texts(assignment, "request"), [])
		self.assertIsNotNone(frappe.db.get_value(ASSIGNMENT, reminder.name, "reminded_on"))
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"reference_doctype": ASSIGNMENT, "reference_name": requests[0].name}
			)
		)

	def test_without_an_email_account_a_person_not_texted_is_not_marked_sent(self):
		self.can_send_email.return_value = False
		frappe.db.set_value("Ministry", self.position.ministry, "team_reminder_days", 7)
		assignment = make_team_assignment(self.sunday, self.position.name, self.ben)

		self.assertEqual(send_team_emails(), 0, "Ben gave no text consent for Serving")

		self.assertIsNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "requested_on"))
		self.assertIsNone(frappe.db.get_value(ASSIGNMENT, assignment.name, "reminded_on"))

	def test_a_church_manager_whose_role_may_not_text_leaves_the_texts_to_the_daily_job(self):
		gateway = self.use_the_real_send_sms(allowed_roles=[])
		ann = make_team_assignment(self.sunday, self.position.name, self.ann)
		ben = make_team_assignment(self.sunday, self.position.name, self.ben)
		frappe.set_user(self.manager())

		self.assertEqual(send_team_emails_now(), 1, "only Ben, who gets no texts")

		self.assertEqual(self.emailed(ben), ["_test_text_team_ben@example.com"])
		self.assertEqual(self.emailed(ann), [])
		self.assertIsNone(frappe.db.get_value(ASSIGNMENT, ann.name, "requested_on"))
		gateway.assert_not_called()

		frappe.set_user("Administrator")
		self.assertEqual(send_team_emails(), 2)
		self.assertEqual(self.emailed(ann), ["_test_text_team_ann@example.com"])
		self.assertEqual(len(self.texts(ann, "request")), 1)
		gateway.assert_called_once()

	def test_a_church_manager_texts_when_sms_settings_allows_the_role(self):
		gateway = self.use_the_real_send_sms(allowed_roles=["Church Manager"])
		assignment = make_team_assignment(self.sunday, self.position.name, self.ann)
		frappe.set_user(self.manager())

		self.assertEqual(send_team_emails_now(), 2)

		self.assertEqual(len(self.texts(assignment, "request")), 1)
		gateway.assert_called_once()

	def use_the_real_send_sms(self, allowed_roles):
		"""Frappe's send_sms with its role check, and a gateway that takes every text."""
		self.send_sms.stop()
		settings = frappe.get_single("SMS Settings")
		settings.update({"message_parameter": "text", "receiver_parameter": "to"})
		settings.set("allowed_roles", [{"role": role} for role in allowed_roles])
		settings.save(ignore_permissions=True)
		return mock.patch(
			"frappe.core.doctype.sms_settings.sms_settings.send_request", return_value=200
		).start()

	def manager(self):
		return ensure_user("_test_text_team_manager@example.com", "Text Manager", roles=("Church Manager",))


class TestServingPurpose(RollbackEachTest):
	def test_the_patch_adds_serving_once_and_it_cannot_be_deleted(self):
		frappe.db.delete("Communication Purpose", {"name": SERVING})

		add_serving_purpose.execute()
		add_serving_purpose.execute()

		self.assertEqual(frappe.db.count("Communication Purpose", {"name": SERVING}), 1)
		with self.assertRaisesRegex(frappe.ValidationError, "used by the app"):
			frappe.delete_doc("Communication Purpose", SERVING)
