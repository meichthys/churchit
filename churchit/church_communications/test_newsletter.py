# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import email
from unittest import mock

import frappe

from churchit.church_communications.consent import allowed
from churchit.church_communications.doctype.church_email.test_church_email import deliver_now
from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.church_communications.newsletter import (
	set_subscribed,
	unsubscribe,
	unsubscribed_emails,
)
from churchit.church_communications.test_unsubscribe_link import click_unsubscribe_link
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	force_single_church,
	make_person,
)

ADDRESS = "_test_newsletter_home@example.com"


class TestChurchEmailSubscription(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		create_communication_purposes()
		cls.person = make_person("_Test Newsletter", "Member", emails=[{"email_address": ADDRESS}]).name

	def click_link(self, method: str = "POST", **params):
		click_unsubscribe_link(method, email=ADDRESS, church=self.church, **params)

	def test_unsubscribing_twice_keeps_one_record(self):
		set_subscribed(ADDRESS, self.church, False)
		set_subscribed(ADDRESS, self.church, False)
		self.assertEqual(
			frappe.db.count("Email Unsubscribe", {"email": ADDRESS, "reference_name": self.church}), 1
		)

		set_subscribed(ADDRESS, self.church, True)
		self.assertNotIn(ADDRESS, unsubscribed_emails(self.church))

	def test_an_old_link_with_no_purpose_stops_that_churchs_emails(self):
		self.click_link()
		self.assertIn(ADDRESS, unsubscribed_emails(self.church))
		self.assertFalse(allowed(self.person, EMAIL, CHURCH_NEWS))

	def test_a_church_news_link_withdraws_only_church_news(self):
		self.click_link(purpose=CHURCH_NEWS)

		self.assertNotIn(ADDRESS, unsubscribed_emails(self.church))
		self.assertFalse(allowed(self.person, EMAIL, CHURCH_NEWS))
		self.assertTrue(allowed(self.person, EMAIL, PASTORAL_CARE))

	def test_opening_the_link_changes_nothing_until_the_button_posts_it(self):
		self.click_link("GET")
		self.assertNotIn(ADDRESS, unsubscribed_emails(self.church))
		self.assertTrue(allowed(self.person, EMAIL, CHURCH_NEWS))
		self.assertIn("<form", frappe.local.message)
		self.assertIn('method="POST"', frappe.local.message)

		self.click_link("POST")
		self.assertIn(ADDRESS, unsubscribed_emails(self.church))

	def test_a_link_for_another_purpose_withdraws_only_that_purpose(self):
		self.click_link(purpose=PASTORAL_CARE)
		self.click_link(purpose=PASTORAL_CARE)

		self.assertNotIn(ADDRESS, unsubscribed_emails(self.church))
		self.assertFalse(allowed(self.person, EMAIL, PASTORAL_CARE))
		self.assertTrue(allowed(self.person, EMAIL, CHURCH_NEWS))
		withdrawals = frappe.get_all(
			"Communication Consent",
			filters={"person": self.person, "purpose": PASTORAL_CARE},
			fields=["status", "method"],
		)
		self.assertEqual(withdrawals, [{"status": "Withdrawn", "method": "Unsubscribe Link"}])

	def test_a_link_for_a_purpose_that_is_gone_still_stops_the_churchs_emails(self):
		self.click_link(purpose="_Test No Such Purpose")
		self.assertIn(ADDRESS, unsubscribed_emails(self.church))

	def test_the_page_after_a_link_says_what_stopped_and_offers_the_way_back(self):
		church_name = frappe.db.get_value("Church", self.church, "church_name")
		for purpose, stopped in (
			(PASTORAL_CARE, f"will no longer receive Pastoral Care emails from {church_name}."),
			(CHURCH_NEWS, f"will no longer receive Church News emails from {church_name}."),
			(None, f"will no longer receive emails from {church_name}."),
		):
			with self.subTest(purpose):
				self.click_link(purpose=purpose)
				self.assertIn(stopped, frappe.local.message)
				self.assertIn("Communication Preferences", frappe.local.message)
				context = frappe.local.response["context"]
				self.assertEqual(
					(context["primary_action"], context["primary_label"]),
					("/preferences", "Choose what you get"),
				)


class TestUnsubscribeLabel(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		create_communication_purposes()
		person = make_person(
			"_Test Label", "Reader", emails=[{"email_address": "_test_label_reader@example.com"}]
		)
		cls.group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Label Group", "members": [{"person": person.name}]}
		).insert(ignore_permissions=True)

	def test_a_church_name_with_an_ampersand_reads_the_same_in_both_parts_of_the_email(self):
		"""Frappe adds the footer link only when it is given words for it, so this runs the real sendmail."""
		ensure(
			"Email Account",
			{"enable_outgoing": 1, "default_outgoing": 1},
			{
				"email_account_name": "_Test Label Outgoing",
				"email_id": "_test_label_outgoing@example.com",
				"service": "GMail",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"no_smtp_authentication": 1,
			},
		)
		church_email = frappe.get_doc(
			{
				"doctype": "Church Email",
				"subject": "_Test Label Email",
				"message": "<p>Hello</p>",
				"send_to": "Group",
				"group": self.group.name,
			}
		).insert()
		frappe.db.set_value("Church Email", church_email.name, {"status": "Sending", "purpose": None})

		church_name = "churchit.church_communications.newsletter.get_church_name"
		with (
			mock.patch(church_name, return_value="_Test Grace & Peace <b>Church</b>"),
			mock.patch.object(frappe.db, "rollback"),
		):
			deliver_now(church_email.name)

		queued = frappe.db.get_value("Email Queue", {"reference_name": church_email.name}, "message")
		parts = {
			part.get_content_type(): part.get_payload(decode=True).decode()
			for part in email.message_from_string(queued).walk()
			if not part.is_multipart()
		}
		self.assertIn("Unsubscribe from all _Test Grace & Peace bChurch/b emails:", parts["text/plain"])
		# Frappe writes the HTML part out again, which escapes the "&" once.
		self.assertIn(
			">Unsubscribe from all _Test Grace &amp; Peace bChurch/b emails</a>", parts["text/html"]
		)
