# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest import mock

import frappe

from churchit.church_communications.consent import allowed
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
from churchit.tests.helpers import (
	RollbackEachTest,
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

	def click_link(self, **params):
		"""Follow the link at the foot of a Church Email, as a guest."""
		frappe.set_user("Guest")
		with mock.patch.object(frappe.db, "commit"):
			unsubscribe(email=ADDRESS, church=self.church, doctype="Church Email", name="x", **params)
		frappe.set_user("Administrator")

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

	def test_a_church_news_link_stops_that_churchs_emails(self):
		self.click_link(purpose=CHURCH_NEWS)
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
