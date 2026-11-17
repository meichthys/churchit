# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Contact page form sends each message to the church whose page it came from."""

from unittest.mock import patch

import frappe
from frappe.utils import set_request

from churchit.church_website import contact
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, make_branch, set_multi_church
from churchit.www import contact as contact_page

SENDER = "_test_contact_visitor@example.com"


class TestContactForm(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch = make_branch("_Test Contact Branch", "TCB", publish=1)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Church", self.root, {"publish": 1, "email": "_test_main@example.com"})
		frappe.db.set_value("Church", self.branch, "email", "_test_branch@example.com")
		frappe.db.set_single_value("Contact Us Settings", {"is_disabled": 0, "forward_to_email": None})
		frappe.db.set_single_value("Contact Us Settings", "send_acknowledgement_email", 0)
		frappe.clear_document_cache("Church", self.root)
		frappe.clear_document_cache("Church", self.branch)
		frappe.local.form_dict = frappe._dict()
		frappe.set_user("Guest")

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def send(self, church=None, **values):
		"""Send a message from the Contact page of *church*; return the thanks and the emailed recipients."""
		frappe.local.form_dict = frappe._dict(church=church) if church else frappe._dict()
		with patch("frappe.sendmail") as sendmail:
			thanks = contact.send_message(
				**{"email": SENDER, "message": "_Test hello\nsecond line", "subject": "General", **values}
			)
		return thanks, [call.kwargs["recipients"] for call in sendmail.call_args_list]

	def stored(self):
		return frappe.get_all(
			"Communication",
			filters={"sender": SENDER},
			fields=["reference_doctype", "reference_name", "subject", "content", "sent_or_received"],
		)

	def test_a_branch_page_sends_the_message_to_the_branch_and_keeps_it_on_the_branch(self):
		thanks, recipients = self.send(self.branch)

		self.assertEqual(recipients, ["_test_branch@example.com"])
		self.assertIn("_Test Contact Branch", thanks)
		[message] = self.stored()
		self.assertEqual((message.reference_doctype, message.reference_name), ("Church", self.branch))
		self.assertEqual(message.sent_or_received, "Received")
		self.assertEqual(message.subject, "Contact page: General")
		self.assertEqual(message.content, "_Test hello<br>second line")

	def test_a_branch_without_an_email_falls_back_to_the_main_church_s_inbox(self):
		frappe.db.set_value("Church", self.branch, "email", None)
		frappe.clear_document_cache("Church", self.branch)
		self.assertEqual(self.send(self.branch)[1], ["_test_main@example.com"])

		frappe.db.set_single_value("Contact Us Settings", "forward_to_email", "_test_inbox@example.com")
		self.assertEqual(self.send(self.branch)[1], ["_test_inbox@example.com"])
		self.assertEqual({row.reference_name for row in self.stored()}, {self.branch})

	def test_the_main_church_keeps_its_forward_to_email(self):
		frappe.db.set_single_value("Contact Us Settings", "forward_to_email", "_test_inbox@example.com")
		self.assertEqual(self.send()[1], ["_test_inbox@example.com"])
		self.assertEqual(self.stored()[0].reference_name, self.root)

	def test_an_unknown_or_unpublished_church_falls_back_to_the_main_church(self):
		hidden = make_branch("_Test Contact Hidden", "TCH", publish=0, email="_test_hidden@example.com")

		for church in (hidden, "CHR-does-not-exist"):
			_thanks, recipients = self.send(church)
			self.assertEqual(recipients, ["_test_main@example.com"], church)
		self.assertEqual({row.reference_name for row in self.stored()}, {self.root})

	def test_the_message_and_its_subject_are_escaped(self):
		self.send(message="<script>alert(1)</script>", subject="<img src=x onerror=alert(1)>")
		[message] = self.stored()
		self.assertEqual(message.content, "&lt;script&gt;alert(1)&lt;/script&gt;")
		self.assertNotIn("<img", message.subject)

	def test_the_acknowledgement_names_the_church(self):
		frappe.db.set_single_value("Contact Us Settings", "send_acknowledgement_email", 1)
		frappe.local.form_dict = frappe._dict(church=self.branch)
		with patch("frappe.sendmail") as sendmail:
			contact.send_message(email=SENDER, message="_Test hello")

		acknowledgement = sendmail.call_args_list[-1].kwargs
		self.assertEqual(acknowledgement["recipients"], SENDER)
		self.assertIn("_Test Contact Branch", acknowledgement["subject"])

	def test_a_bot_that_fills_in_the_hidden_field_sends_and_stores_nothing(self):
		thanks, recipients = self.send(self.branch, website="https://spam.example.com")
		self.assertIn("_Test Contact Branch", thanks)
		self.assertEqual(recipients, [])
		self.assertEqual(self.stored(), [])

	def test_a_bad_email_or_an_empty_message_is_refused(self):
		with self.assertRaises(frappe.InvalidEmailAddressError):
			self.send(email="not an email")
		with self.assertRaises(frappe.ValidationError):
			self.send(message="   ")
		self.assertEqual(self.stored(), [])

	def test_a_switched_off_contact_page_takes_no_message(self):
		frappe.db.set_single_value("Contact Us Settings", "is_disabled", 1)
		with self.assertRaises(frappe.PermissionError):
			self.send()

	def test_a_visitor_can_send_only_a_few_messages_an_hour(self):
		set_request(method="POST", path="/api/method/churchit.church_website.contact.send_message")
		frappe.local.request_ip = f"_test-contact-{frappe.generate_hash(length=8)}"
		self.addCleanup(setattr, frappe.local, "request", None)
		for _attempt in range(10):
			self.send(website="https://spam.example.com")
		with self.assertRaises(frappe.RateLimitExceededError):
			self.send(website="https://spam.example.com")

	def test_the_page_names_the_church_it_shows(self):
		frappe.local.form_dict = frappe._dict(church=self.branch)
		context = contact_page.get_context(frappe._dict())

		self.assertEqual(context["address_title"], "_Test Contact Branch")
		self.assertEqual(context["email_id"], "_test_branch@example.com")
