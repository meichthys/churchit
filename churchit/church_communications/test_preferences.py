# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe

from churchit.church_communications.consent import allowed
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	SMS,
	WITHDRAWN,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.church_communications.newsletter import is_subscribed
from churchit.church_communications.preferences import (
	get_member_preferences,
	set_preference,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
)

MEMBER_EMAIL = "_test_preferences_member@example.com"
MEMBER_PHONE = "+1 555 010 0188"


def send_sms_hooks(methods):
	"""Patch the send_sms hook alone, so an app installed on the bench cannot decide the test."""
	get_hooks = frappe.get_hooks
	return patch(
		"frappe.get_hooks",
		side_effect=lambda hook=None, *args, **kwargs: methods
		if hook == "send_sms"
		else get_hooks(hook, *args, **kwargs),
	)


def set_sms_gateway(url):
	frappe.db.set_single_value("SMS Settings", "sms_gateway_url", url)


def latest_consent(person, channel, purpose):
	return frappe.get_all(
		"Communication Consent",
		filters={"person": person, "channel": channel, "purpose": purpose},
		fields=["status", "method"],
		order_by="recorded_on desc, creation desc",
		limit=1,
	)[0]


class PreferencesTestCase(RollbackEachTest):
	"""A signed-in member with an email and a phone, on a site that sends no texts until a test sets it up.

	`nobody` is an account linked to no Person.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()
		create_communication_purposes()
		cls.user = ensure_user(MEMBER_EMAIL, "_Test Preferences")
		cls.person = make_person(
			"_Test Preferences",
			"Member",
			user=cls.user,
			emails=[{"email_address": MEMBER_EMAIL}],
			phones=[{"phone_number": MEMBER_PHONE}],
		).name
		cls.nobody = ensure_user("_test_preferences_nobody@example.com", "_Test Preferences Nobody")

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		hooks = send_sms_hooks([])
		hooks.start()
		self.addCleanup(hooks.stop)
		set_sms_gateway(None)
		frappe.set_user(self.user)

	def make_member(self, last_name, email, **values):
		"""Another portal member, made by the office while this member stays signed in."""
		frappe.set_user("Administrator")
		user = ensure_user(email, f"_Test {last_name}")
		person = make_person("_Test Preferences", last_name, user=user, **values).name
		frappe.set_user(self.user)
		return person

	def stop_every_email(self):
		"""The member's address stops every email the site sends, as Frappe's own unsubscribe link does."""
		frappe.set_user("Administrator")
		frappe.get_doc(
			{"doctype": "Email Unsubscribe", "email": MEMBER_EMAIL, "global_unsubscribe": 1}
		).insert(ignore_permissions=True)
		frappe.set_user(self.user)


class TestSetPreference(PreferencesTestCase):
	def test_a_switch_records_the_members_choice_for_that_purpose(self):
		result = set_preference(EMAIL, PASTORAL_CARE, 0)

		self.assertEqual(
			latest_consent(self.person, EMAIL, PASTORAL_CARE),
			{"status": WITHDRAWN, "method": "Member Portal"},
		)
		self.assertFalse(allowed(self.person, EMAIL, PASTORAL_CARE))
		self.assertTrue(allowed(self.person, EMAIL, CHURCH_NEWS))
		self.assertEqual(result["message"], "You will not get Pastoral Care by email.")

		set_preference(EMAIL, PASTORAL_CARE, 1)
		self.assertEqual(
			latest_consent(self.person, EMAIL, PASTORAL_CARE), {"status": GIVEN, "method": "Member Portal"}
		)
		self.assertTrue(allowed(self.person, EMAIL, PASTORAL_CARE))

	def test_church_news_by_email_keeps_the_churchs_unsubscribe_in_step(self):
		set_preference(EMAIL, CHURCH_NEWS, 0)
		self.assertFalse(is_subscribed(MEMBER_EMAIL, self.church))
		self.assertEqual(
			latest_consent(self.person, EMAIL, CHURCH_NEWS), {"status": WITHDRAWN, "method": "Member Portal"}
		)

		set_preference(EMAIL, CHURCH_NEWS, 1)
		self.assertTrue(is_subscribed(MEMBER_EMAIL, self.church))
		self.assertTrue(allowed(self.person, EMAIL, CHURCH_NEWS))

	def test_another_purpose_leaves_the_churchs_unsubscribe_alone(self):
		set_preference(EMAIL, PASTORAL_CARE, 0)
		self.assertTrue(is_subscribed(MEMBER_EMAIL, self.church))

	def test_a_yes_lifts_a_stop_on_every_email_and_only_that_purpose_comes_on(self):
		self.stop_every_email()
		self.assertTrue(get_member_preferences()["is_globally_unsubscribed"])

		result = set_preference(EMAIL, PASTORAL_CARE, 1)

		self.assertFalse(result["is_globally_unsubscribed"])
		self.assertFalse(frappe.db.exists("Email Unsubscribe", {"email": MEMBER_EMAIL}))
		self.assertTrue(allowed(self.person, EMAIL, PASTORAL_CARE))
		self.assertFalse(allowed(self.person, EMAIL, CHURCH_NEWS), "the stop still answers for Church News")

	def test_a_no_keeps_a_stop_on_every_email(self):
		self.stop_every_email()

		self.assertTrue(set_preference(EMAIL, PASTORAL_CARE, 0)["is_globally_unsubscribed"])

	def test_texts_can_be_chosen_only_once_the_site_sends_them(self):
		with self.assertRaises(frappe.ValidationError):
			set_preference(SMS, CHURCH_NEWS, 1)

		set_sms_gateway("https://sms.example.com/send")
		result = set_preference(SMS, CHURCH_NEWS, 1)

		self.assertTrue(allowed(self.person, SMS, CHURCH_NEWS))
		self.assertEqual(result["message"], "You will get Church News by text.")
		self.assertTrue(is_subscribed(MEMBER_EMAIL, self.church), "a text choice leaves email alone")

	def test_an_unknown_purpose_is_refused(self):
		with self.assertRaises(frappe.DoesNotExistError):
			set_preference(EMAIL, "_Test No Such Purpose", 1)

	def test_a_member_changes_only_their_own_choices(self):
		other_email = "_test_preferences_other@example.com"
		other = self.make_member("Other", other_email, emails=[{"email_address": other_email}])
		frappe.set_user(other_email)

		# A request may name a person, but the method takes no person to act on.
		frappe.call(set_preference, channel=EMAIL, purpose=PASTORAL_CARE, allow=0, person=self.person)

		self.assertFalse(frappe.db.exists("Communication Consent", {"person": self.person}))
		self.assertEqual(latest_consent(other, EMAIL, PASTORAL_CARE).status, WITHDRAWN)

	def test_an_account_with_no_person_cannot_save(self):
		frappe.set_user(self.nobody)
		with self.assertRaises(frappe.PermissionError):
			set_preference(EMAIL, CHURCH_NEWS, 0)
