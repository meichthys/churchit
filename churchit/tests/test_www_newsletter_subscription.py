# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_communications.newsletter import MEMBER_EMAIL_GROUP
from churchit.tests.helpers import ensure_user
from churchit.www.newsletter_subscription import get_context


class TestNewsletterSubscriptionPage(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			get_context(frappe._dict())
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/newsletter-subscription")

	def test_context_includes_the_subscription_status(self):
		frappe.set_user(ensure_user("_test_newsletter_page@example.com", "_Test Newsletter Page"))
		context = frappe._dict()
		get_context(context)
		self.assertEqual(context.email, "_test_newsletter_page@example.com")
		self.assertEqual(context.newsletter, MEMBER_EMAIL_GROUP)
		self.assertIn("subscribed", context)
