# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Push notifications through `send`, Push consent, and the Push choice on Communication Preferences."""

from unittest import mock

import frappe
from frappe.utils import get_html_for_route

from churchit.church_communications.consent import allowed, allowed_people
from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	PUSH,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	GROUP_MESSAGES,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.church_communications.preferences import get_member_preferences, set_preference
from churchit.church_communications.sending import send
from churchit.church_communications.test_preferences import MEMBER_EMAIL, PreferencesTestCase
from churchit.church_people.group_api import message_group
from churchit.church_people.test_group_leader_page import GroupLeaderTestCase
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

SENDING = "churchit.church_communications.sending"


def turn_push_on(is_on: bool = True):
	"""Push Settings switched on or off for one test. send_push is mocked, so the page needs only a public key."""
	frappe.db.set_single_value(
		"Push Settings", {"enabled": int(is_on), "vapid_public_key": "test-public-key"}
	)


def subscribe(user: str, slug: str):
	frappe.get_doc(
		{
			"doctype": "Push Subscription",
			"user": user,
			"endpoint": f"https://fcm.googleapis.com/fcm/send/{slug}",
			"p256dh": "key",
			"auth": "auth",
		}
	).insert(ignore_permissions=True)


class TestSendPush(RollbackEachTest):
	"""Ann has a User, a subscribed browser and a yes; each of the others lacks one of the three."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, _other = make_two_churches()
		create_communication_purposes()

		def member(first_name, has_user=True):
			user = ensure_user(f"_test_send_push_{first_name.lower()}@example.com", first_name)
			return make_person(
				first_name, "_Test Send Push", church=cls.church, user=user if has_user else None
			).name

		cls.agreed = member("Ann")
		cls.silent = member("Bob")
		cls.unsubscribed = member("Cal")
		cls.no_user = member("Dee", has_user=False)
		record([cls.agreed, cls.unsubscribed, cls.no_user], PUSH, GIVEN, CHURCH_NEWS)
		cls.everyone = [cls.agreed, cls.silent, cls.unsubscribed, cls.no_user]
		cls.source = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test Send Push Group", "church": cls.church}
		).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		turn_push_on()
		for first_name in ("ann", "bob", "dee"):
			subscribe(f"_test_send_push_{first_name}@example.com", first_name)
		self.send_push = mock.patch(f"{SENDING}.send_push", return_value=1).start()
		self.addCleanup(mock.patch.stopall)

	def push(self, key="request", **kwargs):
		return send(
			self.everyone,
			PUSH,
			CHURCH_NEWS,
			self.source,
			key=key,
			subject="News for {{ first_name }}",
			text="Hi {{ first_name }}, {{ code }}",
			context={"code": "X7"},
			**kwargs,
		)

	def copies(self):
		names = frappe.get_all(
			"Communication Link",
			filters={"link_doctype": "Group", "link_name": self.source.name, "parenttype": "Communication"},
			pluck="parent",
		)
		return frappe.get_all(
			"Communication",
			filters={"name": ("in", names)},
			fields=[
				"reference_name",
				"communication_medium",
				"subject",
				"content",
				"send_key",
				"delivery_status",
			],
			order_by="creation asc",
		)

	def test_a_push_reaches_only_people_with_a_user_a_subscription_and_consent(self):
		self.assertEqual(self.push(), {self.agreed})

		self.send_push.assert_called_once_with(
			"_test_send_push_ann@example.com", "News for Ann", "Hi Ann, X7", self.source.get_url()
		)
		[copy] = self.copies()
		self.assertEqual(copy.reference_name, self.agreed)
		self.assertEqual(copy.communication_medium, "Other")
		self.assertEqual((copy.subject, copy.content), ("News for Ann", "Hi Ann, X7"))
		self.assertEqual((copy.send_key, copy.delivery_status), ("request", "Sent"))

	def test_a_push_opens_the_page_the_caller_names(self):
		self.push(url="/groups")

		self.assertEqual(self.send_push.call_args.args[3], "/groups")

	def test_a_push_with_no_text_is_refused(self):
		with self.assertRaisesRegex(frappe.ValidationError, "needs a text"):
			send(self.everyone, PUSH, CHURCH_NEWS, self.source, key="empty", subject="Title only")
		self.send_push.assert_not_called()

	def test_the_same_key_sends_once_and_a_new_key_sends_again(self):
		self.push()
		self.assertEqual(self.push(), set())
		self.assertEqual(self.push(key="reminder"), {self.agreed})
		self.assertEqual(self.send_push.call_count, 2)

	def test_nobody_is_reached_while_push_is_off(self):
		turn_push_on(False)

		self.assertEqual(self.push(), set())
		self.send_push.assert_not_called()
		self.assertEqual(self.copies(), [])

	def test_a_push_no_browser_took_is_marked_error_and_not_sent_again(self):
		self.send_push.return_value = 0

		self.assertEqual(self.push(), set())
		self.assertEqual(self.copies()[0].delivery_status, "Error")
		self.assertEqual(self.push(), set())
		self.assertEqual(self.send_push.call_count, 1)


class TestPushConsent(RollbackEachTest):
	def test_push_needs_a_yes_first_like_texts(self):
		_root, church, _other = make_two_churches()
		create_communication_purposes()
		person = make_person("Eve", "_Test Push Consent", church=church).name

		self.assertTrue(allowed(person, EMAIL, CHURCH_NEWS), "the church contacts by email without asking")
		self.assertEqual(allowed_people([person], PUSH, CHURCH_NEWS), set())

		record([person], PUSH, GIVEN)
		self.assertTrue(allowed(person, PUSH, CHURCH_NEWS))
		record([person], PUSH, WITHDRAWN, CHURCH_NEWS)
		self.assertFalse(allowed(person, PUSH, CHURCH_NEWS))
		self.assertTrue(allowed(person, PUSH, PASTORAL_CARE))


class TestPushPreference(PreferencesTestCase):
	def setUp(self):
		super().setUp()
		turn_push_on()
		frappe.db.delete("Push Subscription", {"user": MEMBER_EMAIL})

	def test_push_shows_once_push_is_on_and_the_member_has_a_subscribed_browser(self):
		self.assertEqual(get_member_preferences()["channels"], [EMAIL])

		subscribe(MEMBER_EMAIL, "member")
		preferences = get_member_preferences()
		self.assertEqual(preferences["channels"], [EMAIL, PUSH])
		self.assertFalse(any(row.allowed[PUSH] for row in preferences["purposes"]), "push needs a yes first")

		turn_push_on(False)
		self.assertEqual(get_member_preferences()["channels"], [EMAIL])

	def test_a_member_gives_and_withdraws_push_for_one_purpose(self):
		with self.assertRaises(frappe.ValidationError):
			set_preference(PUSH, CHURCH_NEWS, 1)

		subscribe(MEMBER_EMAIL, "member")
		result = set_preference(PUSH, CHURCH_NEWS, 1)
		self.assertTrue(allowed(self.person, PUSH, CHURCH_NEWS))
		self.assertFalse(allowed(self.person, PUSH, PASTORAL_CARE))
		self.assertEqual(result["message"], "You will get Church News as a notification.")

		result = set_preference(PUSH, CHURCH_NEWS, 0)
		self.assertFalse(allowed(self.person, PUSH, CHURCH_NEWS))
		self.assertEqual(result["message"], "You will not get Church News as a notification.")
		self.assertTrue(allowed(self.person, EMAIL, CHURCH_NEWS), "a push choice leaves email alone")

	def test_the_page_renders_a_push_switch_for_each_purpose(self):
		subscribe(MEMBER_EMAIL, "member")
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		html = get_html_for_route("preferences")

		self.assertIn('data-channel="Push"', html)
		self.assertIn('<th scope="col" class="channel">Push</th>', html)
		self.assertIn('data-has-push-column="1"', html)

	def test_a_page_with_no_push_column_says_so_to_its_script(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		html = get_html_for_route("preferences")

		self.assertNotIn('data-channel="Push"', html)
		self.assertIn('data-has-push-column="0"', html)


class TestGroupMessagePush(GroupLeaderTestCase):
	def test_a_leader_cannot_send_the_group_a_push(self):
		"""A group message has no plain-text body, so a push would show its subject over an empty body."""
		turn_push_on()
		record([self.leader.name], PUSH, GIVEN, GROUP_MESSAGES)
		subscribe(self.leader_user, "leader")
		frappe.set_user(self.leader_user)
		self.addCleanup(frappe.set_user, "Administrator")

		with mock.patch(f"{SENDING}.send_push") as send_push, self.assertRaises(frappe.ValidationError):
			message_group(self.group.name, "Picnic", "Bring a chair.", channel=PUSH)
		send_push.assert_not_called()
