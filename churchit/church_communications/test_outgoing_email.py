# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A site with no Email Account: staff and members who save a record see no message about it, and the
team still gets its bell entries."""

from unittest.mock import patch

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.email.doctype.notification.notification import Notification

from churchit.church_communications.outgoing_email import NO_ACCOUNT, EmailOnlyWithAnAccount, can_send_email
from churchit.church_people.doctype.care_request.care_request import create_new_care_request_notification
from churchit.portal.care import save_care_request
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person

CARE_USER = "_test_outgoing_care@example.com"


def no_account_messages() -> list[str]:
	return [entry.message for entry in frappe.local.message_log if "outgoing Email Account" in entry.message]


class TestWithoutAnEmailAccount(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.category = ensure("Care Request Type", {"type": "_Test Outgoing Need"})
		cls.person = make_person("_Test Outgoing", "Requester").name
		cls.member = ensure_user("_test_outgoing_member@example.com", "Outgoing Member")
		make_person("_Test Outgoing", "Member", user=cls.member)
		ensure_user(CARE_USER, "Outgoing Care", roles=("Church Pastoral Care",))
		create_new_care_request_notification()

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Email Account", {"default_outgoing": 1}, "default_outgoing", 0)
		frappe.local.outgoing_email_account = {}
		self.addCleanup(setattr, frappe.local, "outgoing_email_account", {})
		self.addCleanup(setattr, frappe.flags, "mute_emails", frappe.flags.mute_emails)
		frappe.flags.mute_emails = False
		config = patch.object(EmailAccount, "find_from_config", return_value=None)
		config.start()
		self.addCleanup(config.stop)
		frappe.local.message_log = []
		self.assertFalse(can_send_email())

	def assert_the_team_was_told(self, request):
		self.assertEqual(no_account_messages(), [])
		self.assertTrue(
			frappe.db.exists(
				"Notification Log",
				{"for_user": CARE_USER, "document_type": "Care Request", "document_name": request},
			)
		)
		self.assertFalse(
			frappe.db.exists(
				"Communication", {"reference_doctype": "Care Request", "reference_name": request}
			),
			"No email went, so the timeline must not say one did",
		)

	def test_a_care_request_saved_in_the_desk(self):
		request = frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": self.person,
				"category": self.category,
				"description": "_Test outgoing",
			}
		).insert()
		self.assert_the_team_was_told(request.name)

	def test_a_care_request_sent_from_the_member_app(self):
		frappe.set_user(self.member)
		request = save_care_request(self.category, "_Test outgoing portal", urgency="Medium")
		frappe.set_user("Administrator")
		self.assert_the_team_was_told(request["name"])

	def test_the_email_of_a_bell_entry_leaves_no_message_and_keeps_the_others(self):
		user = ensure_user("_test_outgoing_mention@example.com", "Outgoing Mention", roles=("Church Staff",))
		frappe.msgprint("_Test another message")
		frappe.msgprint(["_Test a listed message"], as_list=True)
		frappe.get_doc(
			{"doctype": "Notification Log", "for_user": user, "type": "Mention", "subject": "_Test outgoing"}
		).insert(ignore_permissions=True)

		self.assertEqual(no_account_messages(), [])
		messages = [entry.message for entry in frappe.local.message_log]
		self.assertIn("_Test another message", messages)
		self.assertIn(["_Test a listed message"], messages)

	def test_with_an_account_the_notification_still_emails(self):
		frappe.flags.mute_emails = True
		self.assertTrue(can_send_email())
		request = frappe.get_doc(
			{
				"doctype": "Care Request",
				"person": self.person,
				"category": self.category,
				"description": "_Test outgoing with an account",
			}
		).insert()
		self.assertTrue(
			frappe.db.exists(
				"Communication", {"reference_doctype": "Care Request", "reference_name": request.name}
			)
		)
		self.assertEqual(no_account_messages(), [])

	def test_frappe_still_leaves_the_message_without_the_hook(self):
		"""When this fails, Frappe no longer leaves the message: remove outgoing_email and its hooks."""
		user = ensure_user("_test_outgoing_mention@example.com", "Outgoing Mention", roles=("Church Staff",))
		with patch("churchit.church_communications.outgoing_email.forget_no_account_message"):
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Mention",
					"subject": "_Test outgoing",
				}
			).insert(ignore_permissions=True)

		self.assertIn(frappe.utils.html_utils.clean_html(NO_ACCOUNT), no_account_messages())

	def test_frappe_still_fails_the_notification_without_the_extension(self):
		"""When this fails, Frappe handles a missing account itself: remove EmailOnlyWithAnAccount."""
		with patch.object(EmailOnlyWithAnAccount, "send_an_email", Notification.send_an_email):
			request = frappe.get_doc(
				{
					"doctype": "Care Request",
					"person": self.person,
					"category": self.category,
					"description": "_Test outgoing without the extension",
				}
			).insert()

		reference = {"reference_doctype": "Care Request", "reference_name": request.name}
		self.assertTrue(frappe.db.exists("Communication", reference), "Frappe says an email went")
		self.assertFalse(
			frappe.db.exists(
				"Notification Log",
				{"for_user": CARE_USER, "document_type": "Care Request", "document_name": request.name},
			),
			"Frappe skips the bell entry",
		)
