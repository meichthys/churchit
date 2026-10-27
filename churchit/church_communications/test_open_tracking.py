# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from email import message_from_bytes
from email.policy import default

import frappe
from frappe.email.doctype.email_queue.email_queue import EmailQueue, SendMailContext

from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	create_communication_purposes,
)
from churchit.church_communications.sending import Delivery, Recipient
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, force_single_church, make_person

ADDRESS = "_test_open_tracking@example.com"


def built_html(queue: EmailQueue, recipient: str) -> str:
	"""The HTML part of *queue* as Frappe builds it for *recipient* just before it hands it to the mail server."""
	context = SendMailContext(queue)
	context.email_account_doc = queue.get_email_account(raise_error=True)
	message = message_from_bytes(context.build_message(recipient), policy=default)
	return message.get_body(preferencelist=("html",)).get_content()


class TestOpenTracking(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		create_communication_purposes()
		cls.reader = make_person("Reader", "_Test Open Tracking", emails=[{"email_address": ADDRESS}])

	def make_account(self, track_email_status: int) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": "_Test Open Tracking Outgoing",
					"email_id": "_test_open_tracking_outgoing@example.com",
					"service": "GMail",
					"enable_outgoing": 1,
					"default_outgoing": 1,
					"no_smtp_authentication": 1,
					"track_email_status": track_email_status,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def send_copy(self) -> EmailQueue:
		"""Send the reader one Church Email copy and return its Email Queue."""
		email = frappe.get_doc(
			{"doctype": "Church Email", "subject": "_Test Open Tracking", "message": "<p>Hello</p>"}
		).insert()
		Delivery(email).deliver(
			Recipient(self.reader.name, ADDRESS),
			frappe._dict(subject="_Test Open Tracking", message="<p>Hello Reader</p>"),
		)
		return frappe.get_last_doc("Email Queue", filters={"reference_name": email.name})

	def test_a_copy_carries_an_image_that_marks_its_own_communication_read(self):
		account = self.make_account(track_email_status=1)

		queue = self.send_copy()

		self.assertEqual(queue.get_email_account().name, account)
		self.assertEqual(
			frappe.db.get_value("Communication", queue.communication, "reference_name"), self.reader.name
		)
		self.assertIn(
			f"/api/method/frappe.core.doctype.communication.email.mark_email_as_seen?name={queue.communication}",
			built_html(queue, ADDRESS),
		)

	def test_a_copy_carries_no_image_when_track_email_status_is_off(self):
		self.make_account(track_email_status=0)

		queue = self.send_copy()

		self.assertNotIn("mark_email_as_seen", built_html(queue, ADDRESS))
