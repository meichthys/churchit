# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
)

STAFF_ROLE = "Church Manager"


def make_notification(channel, field):
	return frappe.get_doc(
		{
			"doctype": "Notification",
			"name": "_Test Consent Notification",
			"document_type": "Person",
			"event": "New",
			"channel": channel,
			"subject": "_Test",
			"message": "_Test",
			"recipients": [{"receiver_by_document_field": field}, {"receiver_by_role": STAFF_ROLE}],
		}
	)


class TestNotificationConsent(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		create_communication_purposes()
		cls.staff = ensure_user("_test_consent_staff@example.com", "_Test Consent Staff", roles=(STAFF_ROLE,))
		cls.staff_person = make_person(
			"_Test Consent",
			"Staff",
			user=cls.staff,
			emails=[{"email_address": cls.staff}],
			phones=[{"phone_number": "555 010 0101"}],
		)
		frappe.db.set_value("User", cls.staff, "mobile_no", "555 010 0101")

	def setUp(self):
		super().setUp()
		self.member = make_person(
			"_Test Consent",
			"Member",
			emails=[{"email_address": "_test_consent_notified@example.com"}],
			phones=[{"phone_number": "555 010 0102"}],
		)

	def email_recipients(self):
		notification = make_notification("Email", "notification_address,emails")
		recipients, _cc, _bcc = notification.get_list_of_recipients(self.member, {"doc": self.member})
		return recipients

	def sms_receivers(self):
		notification = make_notification("SMS", "phone_number,phones")
		return notification.get_receiver_list(self.member, {"doc": self.member})

	def test_a_member_who_withdrew_email_is_left_out_and_staff_are_kept(self):
		self.assertIn("_test_consent_notified@example.com", self.email_recipients())

		record([self.member.name, self.staff_person.name], EMAIL, WITHDRAWN)
		recipients = self.email_recipients()

		self.assertNotIn("_test_consent_notified@example.com", recipients)
		self.assertIn(self.staff, recipients)

	def test_withdrawing_one_purpose_does_not_stop_notifications(self):
		record([self.member.name], EMAIL, WITHDRAWN, CHURCH_NEWS)
		self.assertIn("_test_consent_notified@example.com", self.email_recipients())

	def test_a_member_gets_texts_only_while_they_agree_and_staff_always_do(self):
		receivers = self.sms_receivers()
		self.assertNotIn("555 010 0102", receivers)
		self.assertIn("555 010 0101", receivers)

		record([self.member.name], SMS, GIVEN)
		self.assertIn("555 010 0102", self.sms_receivers())

		record([self.member.name, self.staff_person.name], SMS, WITHDRAWN)
		receivers = self.sms_receivers()
		self.assertNotIn("555 010 0102", receivers)
		self.assertIn("555 010 0101", receivers)
