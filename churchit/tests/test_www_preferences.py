# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member's /preferences page: a switch per purpose and channel, and a note where one cannot show."""

from unittest.mock import patch

import frappe
from frappe.utils import get_html_for_route

from churchit.church_communications.consent import allowed, get_consent_rows
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	PASTORAL_CARE,
)
from churchit.church_communications.newsletter import set_subscribed
from churchit.church_communications.preferences import set_preference
from churchit.church_communications.test_preferences import (
	MEMBER_EMAIL,
	MEMBER_PHONE,
	PreferencesTestCase,
	set_sms_gateway,
)
from churchit.patches.v1_0 import rename_newsletter_subscription_menu_item
from churchit.tests.helpers import RollbackEachTest, serve_old_member_pages
from churchit.www.preferences import get_context


def page_context():
	context = frappe._dict()
	get_context(context)
	return context


class TestPreferencesPage(PreferencesTestCase):
	def setUp(self):
		super().setUp()
		serve_old_member_pages(self)

	def serve(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		return get_html_for_route("preferences")

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			page_context()
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/preferences")

	def test_a_member_sees_each_purpose_with_their_email_choice(self):
		frappe.set_user("Administrator")
		record([self.person], EMAIL, WITHDRAWN, PASTORAL_CARE)
		frappe.set_user(self.user)

		context = page_context()

		self.assertEqual((context.email, context.phone), (MEMBER_EMAIL, MEMBER_PHONE))
		self.assertEqual(context.channels, [EMAIL])
		choices = {row.purpose: row.allowed for row in context.purposes}
		self.assertEqual(choices[CHURCH_NEWS], {EMAIL: True})
		self.assertEqual(choices[PASTORAL_CARE], {EMAIL: False})
		self.assertFalse(context.is_globally_unsubscribed)

	def test_every_choice_matches_the_consent_rule(self):
		frappe.set_user("Administrator")
		record([self.person], EMAIL, WITHDRAWN, PASTORAL_CARE)
		record([self.person], EMAIL, GIVEN, None)
		record([self.person], EMAIL, WITHDRAWN, CHURCH_NEWS)
		frappe.set_user(self.user)

		for row in page_context().purposes:
			self.assertEqual(row.allowed[EMAIL], allowed(self.person, EMAIL, row.purpose), row.purpose)

	def test_the_consent_rows_are_read_once_for_all_purposes(self):
		frappe.set_user(self.user)
		with patch("churchit.church_communications.consent.get_consent_rows", wraps=get_consent_rows) as read:
			context = page_context()

		self.assertGreater(len(context.purposes), 1)
		self.assertEqual(read.call_count, len(context.channels))

	def test_the_page_renders_a_switch_for_each_choice(self):
		html = self.serve()
		self.assertIn("Communication Preferences", html)
		self.assertIn(MEMBER_EMAIL, html)
		self.assertIn('data-purpose="Church News"', html)
		self.assertNotIn('data-channel="SMS"', html)

	def test_texts_show_once_the_site_sends_them_and_the_member_has_a_phone(self):
		set_sms_gateway("https://sms.example.com/send")
		self.assertEqual(page_context().channels, [EMAIL, SMS])
		self.assertIn('data-channel="SMS"', self.serve())

		texts_off = {row.purpose: row.allowed[SMS] for row in page_context().purposes}
		self.assertFalse(texts_off[CHURCH_NEWS], "texts need a yes first")

	def test_texts_do_not_show_for_a_member_with_no_phone(self):
		set_sms_gateway("https://sms.example.com/send")
		email = "_test_preferences_no_phone@example.com"
		self.make_member("No Phone", email, emails=[{"email_address": email}])
		frappe.set_user(email)

		self.assertEqual(page_context().channels, [EMAIL])

	def test_a_member_with_no_email_sees_a_note_and_no_email_switches(self):
		email = "_test_preferences_no_email@example.com"
		self.make_member("No Email", email)
		frappe.set_user(email)

		context = page_context()
		self.assertIsNone(context.email)
		self.assertEqual(context.channels, [])
		self.assertIn("There is no email address on file for you", self.serve())

	def test_an_account_with_no_person_sees_a_note(self):
		frappe.set_user(self.nobody)

		self.assertIsNone(page_context().person)
		self.assertIn("not linked to a member record", self.serve())

	def test_a_stop_on_every_email_is_explained(self):
		self.stop_every_email()

		self.assertTrue(page_context().is_globally_unsubscribed)
		self.assertIn("You stopped every email to", self.serve())

	def test_a_stop_on_the_churchs_emails_is_explained_until_church_news_is_back_on(self):
		self.assertFalse(page_context().has_stopped_church_emails)
		self.assertIn('id="preferences-church-stopped" hidden', self.serve())

		frappe.set_user("Administrator")
		set_subscribed(MEMBER_EMAIL, self.church, False)
		frappe.set_user(self.user)

		self.assertTrue(page_context().has_stopped_church_emails)
		html = self.serve()
		self.assertIn('id="preferences-church-stopped" >', html)
		self.assertIn("Turn on Church News by email to start them again.", html)

		only_news_starts_them = set_preference(EMAIL, PASTORAL_CARE, 1)["has_stopped_church_emails"]
		self.assertTrue(only_news_starts_them)
		self.assertFalse(set_preference(EMAIL, CHURCH_NEWS, 1)["has_stopped_church_emails"])
		self.assertFalse(page_context().has_stopped_church_emails)

	def test_church_news_off_stops_only_news_and_the_page_says_so(self):
		self.assertFalse(set_preference(EMAIL, CHURCH_NEWS, 0)["has_stopped_church_emails"])
		self.assertIn("turning off Church News stops only news", self.serve())

	def test_a_phone_number_is_never_broken_across_lines(self):
		self.assertIn(f'<span class="text-nowrap">{MEMBER_PHONE}</span>', self.serve())


class TestPreferencesMenuItem(RollbackEachTest):
	def test_the_newsletter_subscription_item_becomes_communication_preferences_once(self):
		routes = (rename_newsletter_subscription_menu_item.OLD_ROUTE, "preferences")
		frappe.db.delete("Portal Menu Item", {"parent": "Portal Settings", "route": ("in", routes)})
		# Inserted straight into the table: saving Portal Settings clears every cache, and the patch saves it once.
		frappe.get_doc(
			{
				"doctype": "Portal Menu Item",
				"parenttype": "Portal Settings",
				"parent": "Portal Settings",
				"parentfield": "menu",
				"idx": 99,
				"title": "Newsletter Subscription",
				"route": "newsletter-subscription",
				"reference_doctype": "Email Group Member",
				"role": "Church User",
				"enabled": 1,
			}
		).db_insert()

		rename_newsletter_subscription_menu_item.execute()
		rename_newsletter_subscription_menu_item.execute()

		menu = frappe.get_doc("Portal Settings").menu
		self.assertFalse([row for row in menu if row.route == "newsletter-subscription"])
		rows = [row for row in menu if row.route == "preferences"]
		self.assertEqual(
			[(row.title, row.role, row.enabled) for row in rows],
			[("Communication Preferences", "Church User", 1)],
		)
