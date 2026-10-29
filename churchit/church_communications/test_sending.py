# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe
from frappe.core.doctype.sms_settings.sms_settings import create_sms_log, validate_receiver_nos
from frappe.tests.utils import FrappeTestCase
from jinja2.exceptions import SecurityError, UndefinedError
from requests import HTTPError, Response

from churchit.church_communications.doctype.church_email.church_email import deliver
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	GIVEN,
	SMS,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.church_communications.newsletter import set_subscribed
from churchit.church_communications.sending import (
	Delivery,
	Recipient,
	can_send_texts,
	check_placeholders,
	get_email_recipients,
	get_people_sent,
	get_text_recipients,
	get_unique_recipients,
	get_values,
	render,
	send_text,
)
from churchit.church_communications.test_preferences import send_sms_hooks
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	force_single_church,
	make_person,
)

ANN = get_values({"first_name": "Ann", "last_name": "Lee", "display_name": "Ann Lee", "full_name": "Ann Lee"})
SENDING = "churchit.church_communications.sending"
FIRST_NUMBER = "555 010 0131"
SECOND_NUMBER = "555 010 0132"


def log_sms(receiver_list, msg, sender_name="", success_msg=True):
	"""What Frappe's gateway does with the texts it takes: log their numbers, cleaned, in SMS Log."""
	numbers = validate_receiver_nos(receiver_list)
	create_sms_log({"message": msg.encode("utf-8"), "receiver_list": numbers}, numbers)


def gateway_error(status):
	"""The error Frappe's gateway raises when the provider answers *status*."""
	response = Response()
	response.status_code = status
	return HTTPError(f"{status} Error", response=response)


def delivery_statuses(email):
	"""Each person's copy of *email*, as {person: delivery status}."""
	copies = frappe.get_all(
		"Communication Link",
		filters={"parenttype": "Communication", "link_doctype": "Church Email", "link_name": email},
		pluck="parent",
	)
	return dict(
		frappe.get_all(
			"Communication",
			filters={"name": ("in", copies)},
			fields=["reference_name", "delivery_status"],
			as_list=True,
		)
	)


class TestPlaceholders(FrappeTestCase):
	def test_each_placeholder_is_filled_in_at_the_top_and_under_doc(self):
		self.assertEqual(render("{{ first_name }} {{ doc.last_name }}", ANN), "Ann Lee")
		self.assertEqual(render("{{ display_name }}", get_values({"first_name": "Ann"})), "")

	def test_names_are_escaped_only_in_an_html_message(self):
		values = get_values({"first_name": "<b>Tom</b> & Ann"})
		self.assertEqual(render("Hi {{ first_name }}", values), "Hi <b>Tom</b> & Ann")
		self.assertEqual(
			render("<p>{{ first_name }}</p>", values, html=True), "<p>&lt;b&gt;Tom&lt;/b&gt; &amp; Ann</p>"
		)

	def test_the_sandbox_cannot_reach_frappe_or_python(self):
		with self.assertRaises(UndefinedError):
			render("{{ frappe.db.sql('select 1') }}", ANN)
		with self.assertRaises(SecurityError):
			render("{{ first_name.__class__.__mro__ }}", ANN)

	def test_a_template_is_refused_unless_it_uses_only_the_persons_names(self):
		refused = (
			"{{ frappe.db.get_value('User', 'Administrator', 'api_secret') }}",
			"{{ doc.name }}",
			"{% for row in doc.items() %}{{ row }}{% endfor %}",
			"{{ first_name.__class__.__mro__ }}",
			"Dear {{ first_name",
		)
		for source in refused:
			with self.subTest(source), self.assertRaises(frappe.ValidationError):
				check_placeholders(source, "Message")

		check_placeholders(
			"{% if display_name %}{{ display_name }}{% endif %} {{ doc.first_name | e }}", "Message"
		)

	def test_the_refusal_names_the_placeholders_that_work(self):
		with self.assertRaisesRegex(frappe.ValidationError, r"\{\{ frappe \}\}.*\{\{ first_name \}\}"):
			check_placeholders("{{ frappe.session.user }}", "Subject")


class TestRecipients(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()

	def test_an_address_is_used_once_whoever_holds_it(self):
		addresses = {"P1": "home@example.com", "P2": "HOME@example.com", "P3": "work@example.com"}
		self.assertEqual(
			get_unique_recipients(["P1", "P2", "P3", "P4"], addresses, "Email Address"),
			[Recipient("P1", "home@example.com"), Recipient("P3", "work@example.com")],
		)

	def test_a_number_is_used_once_however_it_is_written(self):
		numbers = {"P1": "+1 (555) 010-0101", "P2": "15550100101"}
		self.assertEqual(
			get_unique_recipients(["P1", "P2"], numbers, "Phone Number"),
			[Recipient("P1", "+1 (555) 010-0101")],
		)

	def test_email_recipients_leave_out_bad_bounced_and_unsubscribed_addresses(self):
		people = {
			name: make_person(name, "_Test Sending", emails=[{"email_address": address}])
			for name, address in (
				("Good", "_test_sending_good@example.com"),
				("Bounced", "_test_sending_bounced@example.com"),
				("Stopped", "_test_sending_stopped@example.com"),
			)
		}
		frappe.db.set_value("Email Address", people["Bounced"].emails[0].name, "is_bounced", 1)
		set_subscribed("_test_sending_stopped@example.com", self.church, False)

		recipients = get_email_recipients([person.name for person in people.values()], self.church)

		self.assertEqual(recipients, [Recipient(people["Good"].name, "_test_sending_good@example.com")])

	def test_text_recipients_are_at_their_primary_phone(self):
		person = make_person(
			"Texter",
			"_Test Sending",
			phones=[{"phone_number": "555 0101"}, {"phone_number": "555 0102", "is_primary": 1}],
		)
		self.assertEqual(get_text_recipients([person.name]), [Recipient(person.name, "555 0102")])


class TestTextsSetUp(FrappeTestCase):
	def test_texts_need_a_gateway_or_an_app_that_sends_them(self):
		with (
			mock.patch("frappe.get_hooks", return_value=[]),
			mock.patch("frappe.db.get_single_value", return_value=None),
		):
			self.assertFalse(can_send_texts())
		with mock.patch("frappe.db.get_single_value", return_value="https://sms.example.com/send"):
			self.assertTrue(can_send_texts())
		with mock.patch("frappe.get_hooks", return_value=["my_app.sms.send"]):
			self.assertTrue(can_send_texts())


class TestTextDelivery(RollbackEachTest):
	"""A text that does not leave is marked Error, is not counted, and is not sent again."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		ensure("Member Status", {"status": "Active"})
		create_communication_purposes()
		cls.first = make_person("First", "_Test Sending Text", phones=[{"phone_number": FIRST_NUMBER}])
		cls.second = make_person("Second", "_Test Sending Text", phones=[{"phone_number": SECOND_NUMBER}])
		record([cls.first.name, cls.second.name], SMS, GIVEN, CHURCH_NEWS)

	def setUp(self):
		super().setUp()
		for patcher in (send_sms_hooks([]), mock.patch.object(frappe.db, "commit")):
			patcher.start()
			self.addCleanup(patcher.stop)
		self.text = frappe.get_doc(
			{
				"doctype": "Church Email",
				"channel": "Text Message",
				"send_to": "Chosen People",
				"people": [{"person": self.first.name}, {"person": self.second.name}],
				"subject": "_Test Sending Text",
				"message": "<p>Hello</p>",
				"text_message": "Hi {{ first_name }}",
			}
		).insert()

	def deliver(self, send_sms):
		"""Run the delivery job with *send_sms* as Frappe's sender, and return the mock."""
		frappe.db.set_value("Church Email", self.text.name, "status", "Sending")
		with mock.patch(f"{SENDING}.send_sms", side_effect=send_sms) as sender:
			deliver(self.text.name)
		return sender

	def test_a_text_in_the_sms_log_is_sent_and_counted(self):
		self.deliver(log_sms)

		self.assertEqual(
			delivery_statuses(self.text.name), {self.first.name: "Sent", self.second.name: "Sent"}
		)
		self.assertEqual(frappe.db.get_value("Church Email", self.text.name, "recipients"), 2)

	def test_a_text_missing_from_the_sms_log_is_marked_error_and_not_counted(self):
		def log_only_the_first(receiver_list, msg, **kwargs):
			if receiver_list == [FIRST_NUMBER]:
				log_sms(receiver_list, msg)

		self.deliver(log_only_the_first)

		self.assertEqual(
			delivery_statuses(self.text.name), {self.first.name: "Sent", self.second.name: "Error"}
		)
		self.assertEqual(frappe.db.get_value("Church Email", self.text.name, "recipients"), 1)
		self.assertEqual(get_people_sent(self.text.name), {self.first.name})
		self.assertEqual(
			get_people_sent(self.text.name, include_failed=True), {self.first.name, self.second.name}
		)

	def test_a_failed_text_is_not_sent_again(self):
		self.deliver(lambda receiver_list, msg, **kwargs: None)

		sender = self.deliver(log_sms)

		sender.assert_not_called()
		self.assertEqual(set(delivery_statuses(self.text.name).values()), {"Error"})

	def test_a_text_the_gateway_refuses_leaves_the_others_going(self):
		def refuse_the_first(receiver_list, msg, **kwargs):
			if receiver_list == [FIRST_NUMBER]:
				raise gateway_error(400)
			log_sms(receiver_list, msg)

		self.deliver(refuse_the_first)

		self.assertEqual(
			delivery_statuses(self.text.name), {self.first.name: "Error", self.second.name: "Sent"}
		)
		self.assertEqual(frappe.db.get_value("Church Email", self.text.name, "recipients"), 1)

	def test_a_gateway_that_fails_every_text_stops_the_delivery(self):
		"""A wrong password or an outage is not about one number, so the delivery stops and resumes later."""
		with mock.patch(f"{SENDING}.send_sms", side_effect=gateway_error(401)):
			with self.assertRaises(HTTPError):
				Delivery(self.text).send_all()


class TestSendText(RollbackEachTest):
	def test_an_app_that_sends_texts_needs_no_sms_log(self):
		with send_sms_hooks(["my_app.sms.send"]), mock.patch(f"{SENDING}.send_sms"):
			self.assertTrue(send_text(FIRST_NUMBER, "Hi"))

	def test_frappes_gateway_takes_or_refuses_each_text(self):
		frappe.db.set_single_value(
			"SMS Settings",
			{
				"sms_gateway_url": "https://sms.example.com/send",
				"message_parameter": "text",
				"receiver_parameter": "to",
			},
		)
		for status, is_sent in ((200, True), (400, False)):
			response = Response()
			response.status_code = status
			with self.subTest(status), send_sms_hooks([]), mock.patch("requests.get", return_value=response):
				self.assertEqual(send_text(FIRST_NUMBER, "Hi"), is_sent)

	def test_frappes_gateway_must_log_the_number(self):
		with send_sms_hooks([]), mock.patch(f"{SENDING}.send_sms") as sender:
			self.assertFalse(send_text(FIRST_NUMBER, "Hi"))
			sender.side_effect = log_sms
			self.assertTrue(send_text(FIRST_NUMBER, "Hi"))
