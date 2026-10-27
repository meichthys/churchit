# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Web Push: browser subscriptions, one push job per browser, and who reads a subscription."""

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

import frappe
import requests
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid
from py_vapid.utils import b64urldecode, b64urlencode
from pywebpush import WebPushException

from churchit.church_communications import push
from churchit.church_communications.doctype.push_settings.push_settings import generate_keys
from churchit.tests.helpers import RollbackEachTest, ensure_user

SUBSCRIPTION = "Push Subscription"
MEMBER = "_test_push_member@example.com"
OTHER = "_test_push_other@example.com"
SUBJECT = "mailto:office@example.org"


def browser(endpoint: str) -> dict:
	"""What PushSubscription.toJSON() sends from a browser."""
	return {
		"endpoint": endpoint,
		"expirationTime": None,
		"keys": {"p256dh": "key-" + endpoint[-4:], "auth": "auth"},
	}


def endpoint(slug: str) -> str:
	return f"https://fcm.googleapis.com/fcm/send/{slug}"


def real_browser_keys() -> dict:
	"""A p256dh and auth that pywebpush can encrypt a message for."""
	point = (
		ec.generate_private_key(ec.SECP256R1())
		.public_key()
		.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
	)
	return {"p256dh": b64urlencode(point), "auth": b64urlencode(os.urandom(16))}


def gone(status: int) -> WebPushException:
	return WebPushException("Push failed", response=SimpleNamespace(status_code=status, text=""))


class PushTestCase(RollbackEachTest):
	"""Push Settings with keys and switched on, and two signed-in members."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_user(MEMBER, "_Test Push Member")
		ensure_user(OTHER, "_Test Push Other")

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		frappe.set_user("Administrator")
		frappe.db.delete(SUBSCRIPTION)
		settings = frappe.get_single("Push Settings")
		settings.update({"enabled": 0, "vapid_subject": SUBJECT, "vapid_public_key": None})
		settings.save()
		generate_keys()
		frappe.db.set_single_value("Push Settings", "enabled", 1)
		header = patch("frappe.get_request_header", return_value="Test Browser")
		header.start()
		self.addCleanup(header.stop)

	def subscribe_as(self, user: str, slug: str) -> str:
		frappe.set_user(user)
		push.subscribe(json.dumps(browser(endpoint(slug))))
		frappe.set_user("Administrator")
		return frappe.db.get_value(SUBSCRIPTION, {"endpoint": endpoint(slug)}, "name")


class TestSendPush(PushTestCase):
	def send(self, *args, **kwargs):
		"""send_push, then each job it queued, with the push service mocked."""
		with patch("frappe.enqueue") as enqueue:
			sent = push.send_push(*args, **kwargs)
		with patch("pywebpush.webpush") as webpush:
			for call in enqueue.call_args_list:
				self.assertEqual((call.kwargs["queue"], call.kwargs["enqueue_after_commit"]), ("short", True))
				push.deliver(call.kwargs["subscription"], call.kwargs["payload"])
		return sent, webpush

	def pop_error_log(self, subscription: str) -> list[str]:
		"""The Error Log text about *subscription*, deleted: Error Log is MyISAM, so a rollback keeps it."""
		filters = {"reference_doctype": SUBSCRIPTION, "reference_name": subscription}
		log = frappe.get_all("Error Log", filters=filters, pluck="error")
		frappe.db.delete("Error Log", filters)
		return log

	def test_one_push_per_subscription_of_the_user(self):
		self.subscribe_as(MEMBER, "phone")
		self.subscribe_as(MEMBER, "laptop")
		self.subscribe_as(OTHER, "other")

		sent, webpush = self.send(MEMBER, "Rota", "You serve on Sunday.", "/ministry-team")

		self.assertEqual(sent, 2)
		self.assertEqual(webpush.call_count, 2)
		reached = {call.args[0]["endpoint"] for call in webpush.call_args_list}
		self.assertEqual(reached, {endpoint("phone"), endpoint("laptop")})
		call = webpush.call_args_list[0]
		self.assertEqual(
			json.loads(call.args[1]),
			{"title": "Rota", "body": "You serve on Sunday.", "url": "/ministry-team"},
		)
		private_key = frappe.get_single("Push Settings").get_password("vapid_private_key")
		self.assertEqual(call.kwargs["vapid_private_key"], private_key)
		self.assertEqual(call.kwargs["vapid_claims"], {"sub": SUBJECT})
		self.assertEqual(call.kwargs["ttl"], 86400)

	def test_a_subscription_the_push_service_forgot_is_deleted(self):
		for status in (404, 410):
			name = self.subscribe_as(MEMBER, f"gone-{status}")
			with patch("pywebpush.webpush", side_effect=gone(status)), patch("frappe.log_error") as log_error:
				push.deliver(name, "{}")
			self.assertFalse(frappe.db.exists(SUBSCRIPTION, name))
			log_error.assert_not_called()

	def test_another_error_is_logged_once_and_keeps_the_subscription(self):
		name = self.subscribe_as(MEMBER, "busy")
		with patch("pywebpush.webpush", side_effect=gone(500)), patch("frappe.log_error") as log_error:
			push.deliver(name, "{}")
		self.assertTrue(frappe.db.exists(SUBSCRIPTION, name))
		log_error.assert_called_once()

	def test_a_refusal_log_holds_no_endpoint_keys_or_signature(self):
		keys = real_browser_keys()
		frappe.set_user(MEMBER)
		push.subscribe({"endpoint": endpoint("secret-token"), "keys": keys})
		frappe.set_user("Administrator")
		name = frappe.db.get_value(SUBSCRIPTION, {"endpoint": endpoint("secret-token")}, "name")
		refusal = requests.Response()
		refusal.status_code, refusal.reason = 500, "Internal Server Error"
		refusal._content = endpoint("secret-token").encode()

		with patch("requests.post", return_value=refusal):
			push.deliver(name, push.get_payload("Rota", "Private text", None))

		log = self.pop_error_log(name)
		self.assertEqual(len(log), 1)
		self.assertIn("HTTP 500", log[0])
		for secret in ("secret-token", keys["p256dh"], keys["auth"], "vapid t=", "Private text"):
			self.assertNotIn(secret, log[0])

	def test_a_push_service_that_does_not_answer_is_logged_once(self):
		name = self.subscribe_as(MEMBER, "slow")
		with patch("pywebpush.webpush", side_effect=requests.Timeout("fcm.googleapis.com")):
			push.deliver(name, "{}")
		log = self.pop_error_log(name)
		self.assertEqual(len(log), 1)
		self.assertIn("Timeout", log[0])
		self.assertNotIn("fcm.googleapis.com", log[0])
		self.assertTrue(frappe.db.exists(SUBSCRIPTION, name))

	def test_nothing_is_sent_while_push_is_off(self):
		self.subscribe_as(MEMBER, "phone")
		frappe.db.set_single_value("Push Settings", "enabled", 0)
		sent, webpush = self.send(MEMBER, "Rota", "Text")
		self.assertEqual(sent, 0)
		webpush.assert_not_called()

	def test_the_body_is_cut_to_1000_characters(self):
		self.subscribe_as(MEMBER, "phone")
		_sent, webpush = self.send(MEMBER, "Long", "x" * 1500)
		self.assertEqual(len(json.loads(webpush.call_args.args[1])["body"]), 1000)

	def test_a_long_body_in_any_script_fits_one_push_message(self):
		self.subscribe_as(MEMBER, "phone")
		for text in ("Привет мир " * 100, "祈祷" * 600, "🙏" * 1200, '"\\' * 600):
			_sent, webpush = self.send(MEMBER, "Prayer", text)
			payload = webpush.call_args.args[1]
			self.assertLessEqual(len(payload.encode()), push.MAX_PAYLOAD)
			self.assertTrue(text.startswith(json.loads(payload)["body"]))

	def test_the_url_stays_on_this_site(self):
		self.subscribe_as(MEMBER, "phone")
		site_url = frappe.utils.get_url("/preferences")
		_sent, webpush = self.send(MEMBER, "Here", "Text", site_url)
		self.assertEqual(json.loads(webpush.call_args.args[1])["url"], site_url)
		for url in (
			"https://evil.example.com/",
			"//evil.example.com/",
			"/\\evil.example.com",
			"javascript:alert(1)",
		):
			with self.assertRaises(ValueError, msg=url):
				push.send_push(MEMBER, "Away", "Text", url)


class TestSubscribe(PushTestCase):
	def test_a_second_subscribe_updates_the_row_of_its_endpoint(self):
		name = self.subscribe_as(MEMBER, "phone")
		frappe.db.set_value(SUBSCRIPTION, name, "last_used", "2026-01-01 00:00:00")

		self.assertEqual(self.subscribe_as(MEMBER, "phone"), name)

		row = frappe.db.get_value(SUBSCRIPTION, name, ["user", "user_agent", "last_used"], as_dict=True)
		self.assertEqual((row.user, row.user_agent), (MEMBER, "Test Browser"))
		self.assertGreater(str(row.last_used), "2026-01-01 00:00:00")
		self.assertEqual(frappe.db.count(SUBSCRIPTION, {"endpoint": endpoint("phone")}), 1)

	def test_a_browser_moves_to_whoever_signs_in_on_it(self):
		name = self.subscribe_as(MEMBER, "shared")
		self.assertEqual(self.subscribe_as(OTHER, "shared"), name)
		self.assertEqual(frappe.db.get_value(SUBSCRIPTION, name, "user"), OTHER)

	def test_a_user_keeps_only_the_browsers_used_last(self):
		for number in range(push.MAX_BROWSERS):
			name = self.subscribe_as(MEMBER, f"browser-{number}")
			frappe.db.set_value(SUBSCRIPTION, name, "last_used", f"2026-01-{number + 1:02d} 00:00:00")
		self.subscribe_as(OTHER, "other")

		self.subscribe_as(MEMBER, "newest")

		kept = set(frappe.get_all(SUBSCRIPTION, filters={"user": MEMBER}, pluck="endpoint"))
		self.assertEqual(len(kept), push.MAX_BROWSERS)
		self.assertNotIn(endpoint("browser-0"), kept)
		self.assertIn(endpoint("newest"), kept)
		self.assertTrue(frappe.db.exists(SUBSCRIPTION, {"user": OTHER}))

	def test_a_deleted_or_disabled_user_keeps_no_browser(self):
		leaver = ensure_user("_test_push_leaver@example.com", "_Test Push Leaver")
		self.subscribe_as(leaver, "leaver")
		self.subscribe_as(MEMBER, "stays")

		frappe.delete_doc("User", leaver)

		self.assertFalse(frappe.db.exists(SUBSCRIPTION, {"user": leaver}))
		self.assertTrue(frappe.db.exists(SUBSCRIPTION, {"user": MEMBER}))

		user = frappe.get_doc("User", MEMBER)
		user.enabled = 0
		user.save(ignore_permissions=True)
		self.assertFalse(frappe.db.exists(SUBSCRIPTION, {"user": MEMBER}))

	def test_subscribe_refuses_guests(self):
		frappe.set_user("Guest")
		for method in (push.subscribe, push.unsubscribe):
			with self.assertRaises(frappe.PermissionError):
				frappe.is_whitelisted(method)

	def test_subscribe_refuses_while_push_is_off(self):
		frappe.db.set_single_value("Push Settings", "enabled", 0)
		with self.assertRaises(frappe.ValidationError):
			self.subscribe_as(MEMBER, "phone")

	def test_subscribe_refuses_an_endpoint_that_is_no_push_service(self):
		frappe.set_user(MEMBER)
		for url in (
			"https://intranet.example.com/push",
			"http://fcm.googleapis.com/fcm/send/x",
			# requests posts these to 127.0.0.1 and internal.host, though urlsplit reads fcm.googleapis.com.
			"https://127.0.0.1\\@fcm.googleapis.com/x",
			"https://internal.host:8443\\@fcm.googleapis.com/x",
			"https://user@fcm.googleapis.com/x",
			"https://fcm.googleapis.com:8443/x",
		):
			with self.assertRaises(frappe.ValidationError, msg=url):
				push.subscribe(browser(url))

	def test_subscribe_refuses_a_malformed_subscription(self):
		frappe.set_user(MEMBER)
		for subscription in (
			"[1]",
			{"endpoint": endpoint("nokeys")},
			{"endpoint": endpoint("x"), "keys": "abc"},
			{"endpoint": ["https://fcm.googleapis.com/x"], "keys": {"p256dh": "key", "auth": "auth"}},
			{"endpoint": endpoint("x"), "keys": {"p256dh": "k" * 141, "auth": "auth"}},
			{"endpoint": endpoint("x"), "keys": {"p256dh": "key", "auth": 1}},
		):
			with self.assertRaises(frappe.ValidationError, msg=subscription):
				push.subscribe(subscription)
		self.assertFalse(frappe.db.count(SUBSCRIPTION))

	def test_unsubscribe_deletes_only_the_users_own_row(self):
		mine = self.subscribe_as(MEMBER, "mine")
		theirs = self.subscribe_as(OTHER, "theirs")
		frappe.set_user(MEMBER)

		push.unsubscribe(endpoint("theirs"))
		push.unsubscribe(endpoint("mine"))

		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists(SUBSCRIPTION, mine))
		self.assertTrue(frappe.db.exists(SUBSCRIPTION, theirs))


class TestSubscriptionAccess(PushTestCase):
	def test_a_user_reads_only_their_own_subscriptions(self):
		mine = self.subscribe_as(MEMBER, "mine")
		theirs = self.subscribe_as(OTHER, "theirs")
		frappe.set_user(MEMBER)

		self.assertEqual(frappe.get_list(SUBSCRIPTION, pluck="name"), [mine])
		self.assertTrue(frappe.has_permission(SUBSCRIPTION, "read", doc=mine))
		self.assertFalse(frappe.has_permission(SUBSCRIPTION, "read", doc=theirs))
		self.assertFalse(frappe.has_permission(SUBSCRIPTION, "delete", doc=theirs))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(SUBSCRIPTION, theirs).check_permission("read")

	def test_a_system_manager_reads_every_subscription(self):
		mine = self.subscribe_as(MEMBER, "mine")
		theirs = self.subscribe_as(OTHER, "theirs")
		manager = ensure_user(
			"_test_push_manager@example.com", "_Test Push Manager", roles=("System Manager",)
		)
		frappe.set_user(manager)

		self.assertEqual(set(frappe.get_list(SUBSCRIPTION, pluck="name")), {mine, theirs})
		self.assertTrue(frappe.has_permission(SUBSCRIPTION, "read", doc=theirs))


class TestPushSettings(PushTestCase):
	def test_generate_keys_makes_a_key_pair_browsers_accept(self):
		settings = frappe.get_single("Push Settings")
		public_key = settings.vapid_public_key
		private_key = settings.get_password("vapid_private_key")

		# The applicationServerKey format: an uncompressed P-256 point, base64url without padding.
		self.assertNotIn("=", public_key)
		point = b64urldecode(public_key.encode())
		self.assertEqual((len(point), point[0]), (65, 4))
		# The private key is the one pywebpush signs with, and it belongs to the public key.
		signed = Vapid.from_string(private_key).sign({"sub": SUBJECT, "aud": "https://fcm.googleapis.com"})
		self.assertTrue(signed["Authorization"].endswith(f"k={public_key}"))

	def test_generate_keys_keeps_existing_keys(self):
		public_key = frappe.db.get_single_value("Push Settings", "vapid_public_key")
		with self.assertRaises(frappe.ValidationError):
			generate_keys()
		self.assertEqual(frappe.db.get_single_value("Push Settings", "vapid_public_key"), public_key)

	def test_only_a_system_manager_generates_keys(self):
		frappe.set_user(MEMBER)
		with self.assertRaises(frappe.PermissionError):
			generate_keys()

	def test_push_turns_on_only_with_keys_and_a_mailto_address(self):
		settings = frappe.get_single("Push Settings")
		settings.vapid_subject = "office@example.org"
		with self.assertRaises(frappe.ValidationError):
			settings.save()

		settings.reload()
		settings.update({"enabled": 0, "vapid_public_key": None})
		settings.save()
		settings.enabled = 1
		with self.assertRaises(frappe.ValidationError):
			settings.save()

	def test_the_page_gets_the_public_key_and_never_the_private_key(self):
		from churchit.www.preferences import get_context

		frappe.set_user(MEMBER)
		context = frappe._dict()
		get_context(context)
		frappe.set_user("Administrator")
		settings = frappe.get_single("Push Settings")
		self.assertEqual(context.push_public_key, settings.vapid_public_key)
		self.assertNotIn(settings.get_password("vapid_private_key"), frappe.as_json(context))

		frappe.db.set_single_value("Push Settings", "enabled", 0)
		frappe.set_user(MEMBER)
		get_context(context)
		self.assertIsNone(context.push_public_key)
