# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_communications.newsletter import (
	MEMBER_EMAIL_GROUP,
	get_subscription_status,
	set_subscription,
	sync_member_email_group,
)
from churchit.tests.helpers import ensure, ensure_user, make_person


class TestNewsletter(FrappeTestCase):
	def setUp(self):
		ensure("Email Group", {"title": MEMBER_EMAIL_GROUP})
		self.user = ensure_user("_test_subscriber@example.com", "_Test Subscriber")
		self.person = make_person("_Test Newsletter", "Member", user=self.user)
		self.person.append("emails", {"email_address": "_test_work@example.com"})
		self.person.append("emails", {"email_address": "_test_home@example.com", "is_primary": 1})
		self.person.save(ignore_permissions=True)
		frappe.db.delete("Email Group Member", {"email": ["like", "_test_%@example.com"]})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _member(self, email):
		return frappe.db.get_value(
			"Email Group Member",
			{"email_group": MEMBER_EMAIL_GROUP, "email": email},
			["name", "unsubscribed"],
			as_dict=True,
		)

	def test_sync_adds_each_persons_primary_email_only(self):
		sync_member_email_group()
		self.assertTrue(self._member("_test_home@example.com"))
		self.assertIsNone(self._member("_test_work@example.com"))

	def test_sync_keeps_unsubscribed_members_unsubscribed(self):
		sync_member_email_group()
		member = self._member("_test_home@example.com")
		frappe.db.set_value("Email Group Member", member.name, "unsubscribed", 1)

		sync_member_email_group()
		self.assertTrue(self._member("_test_home@example.com").unsubscribed)

	def test_status_reflects_the_linked_persons_primary_email(self):
		frappe.set_user(self.user)
		self.assertEqual(
			get_subscription_status(),
			{"email": "_test_home@example.com", "subscribed": False, "newsletter": MEMBER_EMAIL_GROUP},
		)
		sync_member_email_group()
		self.assertTrue(get_subscription_status()["subscribed"])

	def test_status_falls_back_to_the_user_email(self):
		user = ensure_user("_test_personless@example.com", "_Test Personless")
		frappe.set_user(user)
		self.assertEqual(get_subscription_status()["email"], "_test_personless@example.com")

	def test_guests_have_no_status(self):
		frappe.set_user("Guest")
		self.assertIsNone(get_subscription_status()["email"])

	def test_set_subscription_toggles_the_unsubscribed_flag(self):
		frappe.set_user(self.user)
		self.assertEqual(set_subscription(1), {"subscribed": True})
		self.assertFalse(self._member("_test_home@example.com").unsubscribed)

		self.assertEqual(set_subscription("0"), {"subscribed": False})
		self.assertTrue(self._member("_test_home@example.com").unsubscribed)

	def test_set_subscription_needs_an_email_on_file(self):
		frappe.set_user("Guest")
		with self.assertRaises(ValidationError):
			set_subscription(1)
