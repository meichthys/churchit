# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A group leader's message to their group: sent through X1 with the Group Messages purpose."""

from unittest import mock

import frappe
from frappe.handler import execute_cmd

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	GROUP_MESSAGES,
)
from churchit.church_communications.test_preferences import send_sms_hooks
from churchit.church_communications.test_sending import log_sms
from churchit.church_people.group_api import message_group
from churchit.church_people.test_group_leader_page import GroupLeaderTestCase
from churchit.tests.helpers import ensure_user


class TestMessageGroup(GroupLeaderTestCase):
	def setUp(self):
		super().setUp()
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.can_send_email = mock.patch(
			"churchit.church_people.group_api.can_send_email", return_value=True
		).start()
		self.addCleanup(mock.patch.stopall)

	def send(self, subject="Picnic", message="Bring a chair.", user=None, **kwargs):
		frappe.set_user(user or self.leader_user)
		try:
			return message_group(self.group.name, subject, message, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def copies(self):
		"""(person, send key) of each Communication linked to the group."""
		names = frappe.get_all(
			"Communication Link",
			filters={"link_doctype": "Group", "link_name": self.group.name, "parenttype": "Communication"},
			pluck="parent",
		)
		return frappe.get_all(
			"Communication",
			filters={"name": ("in", names)},
			fields=["reference_name", "send_key", "communication_medium"],
			order_by="creation asc",
		)

	def test_each_living_member_who_allows_it_gets_one_copy(self):
		record([self.private.name], EMAIL, WITHDRAWN, GROUP_MESSAGES)

		self.assertEqual(self.send(), 2)

		self.assertEqual(
			sorted(copy.reference_name for copy in self.copies()),
			sorted([self.leader.name, self.sharer.name]),
		)
		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Group", "reference_name": self.group.name, "comment_type": "Info"},
			pluck="content",
		)
		self.assertEqual(len(comments), 1)
		self.assertIn("Lee _Test Page", comments[0])
		self.assertIn("Picnic", comments[0])

	def test_the_leaders_text_is_never_template_source(self):
		self.send(subject="{{ frappe.session.user }}", message="<b>{{ frappe.session.user }}</b>")

		email = next(
			call.kwargs
			for call in self.sendmail.call_args_list
			if call.kwargs["recipients"] == ["_test_page_sharer@example.com"]
		)
		self.assertEqual(email["subject"], "{{ frappe.session.user }}")
		self.assertIn("&lt;b&gt;{{ frappe.session.user }}&lt;/b&gt;", email["message"])
		self.assertIn("Lee _Test Page", email["message"])

	def test_two_messages_with_the_same_text_both_send(self):
		self.send()
		self.send()

		keys = [copy.send_key for copy in self.copies() if copy.reference_name == self.sharer.name]
		self.assertEqual(len(keys), 2)
		self.assertNotEqual(keys[0], keys[1])

	def test_a_member_who_does_not_lead_the_group_is_refused(self):
		member_user = ensure_member_user(self.sharer)

		with self.assertRaises(frappe.PermissionError):
			self.send(user=member_user)
		with self.assertRaises(frappe.PermissionError):
			self.send(user=self.other_leader_user)
		self.assertEqual(self.copies(), [])

	def test_a_get_is_refused(self):
		"""A GET carries no CSRF token, so another site could message a group from a leader's browser."""
		frappe.set_user(self.leader_user)
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(group=self.group.name, subject="Picnic", message="Hello")

		with self.assertRaises(frappe.PermissionError):
			execute_cmd("churchit.church_people.group_api.message_group")
		frappe.set_user("Administrator")
		self.assertEqual(self.copies(), [])

	def test_an_email_waits_for_an_outgoing_email_account(self):
		self.can_send_email.return_value = False

		with self.assertRaisesRegex(frappe.ValidationError, "cannot send email"):
			self.send()
		self.assertEqual(self.copies(), [])

	def test_a_text_goes_only_when_the_site_can_send_texts(self):
		with mock.patch("churchit.church_people.group_api.can_send_texts", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				self.send(channel=SMS)

		record([self.sharer.name], SMS, GIVEN, GROUP_MESSAGES)
		for patcher in (
			send_sms_hooks([]),
			mock.patch("churchit.church_communications.sending.send_sms", side_effect=log_sms),
			mock.patch("churchit.church_people.group_api.can_send_texts", return_value=True),
			mock.patch("frappe.db.commit"),
		):
			patcher.start()

		self.assertEqual(self.send(channel=SMS), 1)
		self.assertEqual(
			[(copy.reference_name, copy.communication_medium) for copy in self.copies()],
			[(self.sharer.name, "SMS")],
		)


def ensure_member_user(person):
	user = ensure_user("_test_page_member@example.com", "_Test Page Member")
	frappe.db.set_value("Person", person.name, "user", user)
	return user
