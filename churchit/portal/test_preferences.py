# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The communication preferences of the member app: a choice per purpose and channel."""

from unittest.mock import patch

import frappe

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
from churchit.church_website.pages import sync_page_switches
from churchit.portal import account


class TestPreferencesApi(PreferencesTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.addClassCleanup(frappe.clear_cache)
		sync_page_switches()

	def choices(self) -> dict:
		return {row["purpose"]: row["allowed"] for row in account.get_preferences()["purposes"]}

	def test_a_member_sees_each_purpose_with_their_email_choice(self):
		frappe.set_user("Administrator")
		record([self.person], EMAIL, WITHDRAWN, PASTORAL_CARE)
		frappe.set_user(self.user)

		result = account.get_preferences()

		self.assertEqual((result["email"], result["phone"]), (MEMBER_EMAIL, MEMBER_PHONE))
		self.assertEqual(result["channels"], [EMAIL])
		self.assertEqual(self.choices()[CHURCH_NEWS], {EMAIL: True})
		self.assertEqual(self.choices()[PASTORAL_CARE], {EMAIL: False})
		self.assertFalse(result["is_globally_unsubscribed"])
		self.assertEqual(result["person"], self.person)

	def test_every_choice_matches_the_consent_rule(self):
		frappe.set_user("Administrator")
		record([self.person], EMAIL, WITHDRAWN, PASTORAL_CARE)
		record([self.person], EMAIL, GIVEN, None)
		record([self.person], EMAIL, WITHDRAWN, CHURCH_NEWS)
		frappe.set_user(self.user)

		for purpose, choice in self.choices().items():
			self.assertEqual(choice[EMAIL], allowed(self.person, EMAIL, purpose), purpose)

	def test_the_consent_rows_are_read_once_for_all_purposes(self):
		with patch("churchit.church_communications.consent.get_consent_rows", wraps=get_consent_rows) as read:
			result = account.get_preferences()

		self.assertGreater(len(result["purposes"]), 1)
		self.assertEqual(read.call_count, len(result["channels"]))

	def test_texts_show_once_the_site_sends_them_and_the_member_has_a_phone(self):
		set_sms_gateway("https://sms.example.com/send")

		self.assertEqual(account.get_preferences()["channels"], [EMAIL, SMS])
		self.assertFalse(self.choices()[CHURCH_NEWS][SMS], "texts need a yes first")

	def test_texts_do_not_show_for_a_member_with_no_phone(self):
		set_sms_gateway("https://sms.example.com/send")
		email = "_test_preferences_no_phone@example.com"
		self.make_member("No Phone", email, emails=[{"email_address": email}])
		frappe.set_user(email)

		self.assertEqual(account.get_preferences()["channels"], [EMAIL])

	def test_a_member_with_no_email_has_no_email_choice(self):
		email = "_test_preferences_no_email@example.com"
		self.make_member("No Email", email)
		frappe.set_user(email)

		result = account.get_preferences()

		self.assertIsNone(result["email"])
		self.assertEqual(result["channels"], [])

	def test_an_account_with_no_person_is_refused(self):
		frappe.set_user(self.nobody)

		with self.assertRaises(frappe.PermissionError):
			account.get_preferences()

	def test_a_stop_on_every_email_is_reported(self):
		self.stop_every_email()

		self.assertTrue(account.get_preferences()["is_globally_unsubscribed"])

	def test_a_stop_on_the_churchs_emails_lasts_until_church_news_is_back_on(self):
		self.assertFalse(account.get_preferences()["has_stopped_church_emails"])

		frappe.set_user("Administrator")
		set_subscribed(MEMBER_EMAIL, self.church, False)
		frappe.set_user(self.user)

		self.assertTrue(account.get_preferences()["has_stopped_church_emails"])
		self.assertTrue(set_preference(EMAIL, PASTORAL_CARE, 1)["has_stopped_church_emails"])
		self.assertFalse(set_preference(EMAIL, CHURCH_NEWS, 1)["has_stopped_church_emails"])
		self.assertFalse(account.get_preferences()["has_stopped_church_emails"])
