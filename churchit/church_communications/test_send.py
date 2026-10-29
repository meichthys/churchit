# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from requests import HTTPError

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.church_communications.newsletter import UNSUBSCRIBE_METHOD
from churchit.church_communications.sending import send
from churchit.church_communications.test_preferences import send_sms_hooks
from churchit.church_communications.test_sending import gateway_error, log_sms
from churchit.tests.helpers import RollbackEachTest, ensure, make_person, make_two_churches

SENDING = "churchit.church_communications.sending"
TEXT = "Hi {{ first_name }}, {{ code }}"


class TestSend(RollbackEachTest):
	"""`send` gives each person who agreed one copy about a record, kept on their timeline, once per key."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, _other = make_two_churches()
		create_communication_purposes()
		cls.agreed = make_person(
			"Ann",
			"_Test Send",
			church=cls.church,
			emails=[{"email_address": "_test_send_ann@example.com"}],
			phones=[{"phone_number": "555 010 0141"}, {"phone_number": "555 010 0142", "is_primary": 1}],
		)
		cls.silent = make_person(
			"Bob", "_Test Send", church=cls.church, phones=[{"phone_number": "555 010 0143"}]
		)
		cls.also_agreed = make_person(
			"Cal", "_Test Send", church=cls.church, phones=[{"phone_number": "555 010 0144"}]
		)
		record([cls.agreed.name, cls.also_agreed.name], SMS, GIVEN, CHURCH_NEWS)
		cls.source = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Send Group", "church": cls.church}
		).insert(ignore_permissions=True)
		cls.template = ensure(
			"Email Template",
			{"name": "_Test Send Template"},
			{
				"doctype": "Email Template",
				"name": "_Test Send Template",
				"subject": "Hello {{ first_name }}",
				"response": "<p>Your code is {{ code }}</p>",
			},
		)

	def setUp(self):
		super().setUp()
		for patcher in (send_sms_hooks([]), mock.patch(f"{SENDING}.send_sms", side_effect=log_sms)):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.sendmail = mock.patch("frappe.sendmail").start()
		self.addCleanup(mock.patch.stopall)

	def text(self, key="request", text=TEXT, **kwargs):
		return send(
			[self.agreed.name, self.silent.name],
			SMS,
			CHURCH_NEWS,
			self.source,
			key=key,
			text=text,
			context={"code": "X7"},
			**kwargs,
		)

	def copies(self):
		"""The Communications made about the source, as dicts."""
		names = frappe.get_all(
			"Communication Link",
			filters={"link_doctype": "Group", "link_name": self.source.name, "parenttype": "Communication"},
			pluck="parent",
		)
		return frappe.get_all(
			"Communication",
			filters={"name": ("in", names)},
			fields=["reference_name", "phone_no", "content", "send_key", "email_template", "delivery_status"],
			order_by="creation asc",
		)

	def test_a_text_goes_only_to_who_agreed_at_their_primary_phone(self):
		self.assertEqual(self.text(), {self.agreed.name})

		[copy] = self.copies()
		self.assertEqual(copy.reference_name, self.agreed.name)
		self.assertEqual(copy.phone_no, "555 010 0142")
		self.assertEqual(copy.content, "Hi Ann, X7")
		self.assertEqual(copy.send_key, "request")
		self.assertEqual(copy.delivery_status, "Sent")

	def test_the_same_key_sends_once_and_a_new_key_sends_again(self):
		self.text()
		self.assertEqual(self.text(), set())
		self.assertEqual(self.text(key="reminder-2026-10-25"), {self.agreed.name})
		self.assertEqual([copy.send_key for copy in self.copies()], ["request", "reminder-2026-10-25"])

	def test_a_template_goes_out_with_the_unsubscribe_link_of_the_sources_church_and_purpose(self):
		sent = send(
			[self.agreed.name],
			EMAIL,
			CHURCH_NEWS,
			self.source,
			template=self.template,
			context={"code": "X7"},
		)

		self.assertEqual(sent, {self.agreed.name})
		email = self.sendmail.call_args.kwargs
		self.assertEqual(email["recipients"], ["_test_send_ann@example.com"])
		self.assertEqual(email["subject"], "Hello Ann")
		self.assertEqual(email["message"], "<p>Your code is X7</p>")
		self.assertEqual((email["reference_doctype"], email["reference_name"]), ("Group", self.source.name))
		self.assertEqual(email["unsubscribe_method"], UNSUBSCRIBE_METHOD)
		self.assertEqual(
			email["unsubscribe_params"],
			{"church": self.church, "purpose": CHURCH_NEWS, "person": self.agreed.name},
		)
		self.assertEqual(self.copies()[0].email_template, self.template)

	def test_an_unknown_placeholder_is_refused_before_any_copy(self):
		with self.assertRaisesRegex(frappe.ValidationError, "unknown"):
			self.text(text="Hi {{ unknown }}")
		self.assertEqual(self.copies(), [])

	def test_a_missing_source_an_unknown_purpose_or_an_unknown_channel_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			send([self.agreed.name], SMS, CHURCH_NEWS, None, text="Hi")
		with self.assertRaises(frappe.ValidationError):
			send([self.agreed.name], SMS, "_Test No Such Purpose", self.source, text="Hi")
		with self.assertRaisesRegex(frappe.ValidationError, "Phone"):
			send([self.agreed.name], "Phone", CHURCH_NEWS, self.source, text="Hi")
		self.assertEqual(self.copies(), [])

	def test_texts_sent_one_person_a_commit_are_not_repeated_after_a_gateway_failure(self):
		"""The caller pattern the docstring asks for: a savepoint stands for each commit of the job."""
		people = [self.agreed.name, self.also_agreed.name]
		texted = []

		def gateway(receiver_list, msg, **kwargs):
			if receiver_list == ["555 010 0144"] and len(texted) == 1:
				texted.append(receiver_list[0])
				raise gateway_error(503)
			texted.append(receiver_list[0])
			log_sms(receiver_list, msg)

		def run_job():
			frappe.db.savepoint("committed")
			try:
				for person in people:
					send([person], SMS, CHURCH_NEWS, self.source, key="reminder", text="Hi")
					frappe.db.savepoint("committed")
			except HTTPError:
				frappe.db.rollback(save_point="committed")
				raise

		with mock.patch(f"{SENDING}.send_sms", side_effect=gateway):
			with self.assertRaises(HTTPError):
				run_job()
			run_job()

		self.assertEqual(texted, ["555 010 0142", "555 010 0144", "555 010 0144"])
		self.assertEqual(sorted(copy.reference_name for copy in self.copies()), sorted(people))
