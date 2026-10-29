# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Web Push for the member app: browser subscriptions and sending one notification to a user's browsers.

pywebpush signs each message with the Push Settings key pair (VAPID) and encrypts it for the browser,
so this module holds no crypto. A browser subscribes on /preferences, which stores one Push
Subscription per endpoint; the service worker (`www/sw.js`) shows the notification and opens its url.
"""

import json
from urllib.parse import urlsplit

import frappe
import pywebpush
import requests
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import get_url, now_datetime
from urllib3.util import parse_url

SETTINGS = "Push Settings"
SUBSCRIPTION = "Push Subscription"
# A push service keeps an undelivered message this long, in seconds.
TTL = 86400
MAX_BODY = 1000
# A push service takes 4096 bytes, encryption included (RFC 8291 leaves 3993 for the payload).
MAX_PAYLOAD = 3800
# The length of a Data field, which holds each key of a subscription.
MAX_KEY = 140
# The push service told us the browser unsubscribed.
GONE = (404, 410)
# A user keeps this many browsers; a new one replaces the one used longest ago.
MAX_BROWSERS = 10
# The push services of the browsers that support Web Push (Chromium builds without Google's keys use
# google.com). The server posts to each endpoint, so any other host would let a member point the
# server at an address of their choice.
PUSH_SERVICES = (
	"fcm.googleapis.com",
	"google.com",
	"push.services.mozilla.com",
	"push.apple.com",
	"notify.windows.com",
)


def is_push_on() -> bool:
	"""True while Push Settings is enabled; enabling it needs the keys and a contact address."""
	return bool(frappe.db.get_single_value(SETTINGS, "enabled"))


def get_public_key() -> str | None:
	"""The key a browser subscribes with (applicationServerKey), while push is on."""
	return frappe.db.get_single_value(SETTINGS, "vapid_public_key") if is_push_on() else None


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60)
def subscribe(subscription: str | dict) -> None:
	"""Keep the browser *subscription* (PushSubscription.toJSON()) for the signed-in user.

	One row per endpoint. An endpoint is one browser, so a row made by another user who signed in
	on the same browser moves to whoever is signed in now. A user keeps at most MAX_BROWSERS rows.
	"""
	if not is_push_on():
		frappe.throw(_("Notifications are not turned on for this site."))

	subscription = frappe.parse_json(subscription)
	if not is_browser_subscription(subscription):
		frappe.throw(_("This browser cannot receive notifications from this site."))

	endpoint, keys = subscription["endpoint"], subscription["keys"]
	name = frappe.db.get_value(SUBSCRIPTION, {"endpoint": endpoint}, "name", for_update=True)
	doc = frappe.get_doc(SUBSCRIPTION, name) if name else frappe.new_doc(SUBSCRIPTION)
	doc.update(
		{
			"user": frappe.session.user,
			"endpoint": endpoint,
			"p256dh": keys["p256dh"],
			"auth": keys["auth"],
			"user_agent": (frappe.get_request_header("User-Agent") or "")[:140],
			"last_used": now_datetime(),
		}
	)
	# Members hold no write right on subscriptions: only this function stores them.
	doc.save(ignore_permissions=True)

	browsers = frappe.get_all(
		SUBSCRIPTION, filters={"user": doc.user}, order_by="last_used desc, creation desc", pluck="name"
	)
	for name in browsers[MAX_BROWSERS:]:
		frappe.delete_doc(SUBSCRIPTION, name, ignore_permissions=True)


@frappe.whitelist(methods=["POST"])
def unsubscribe(endpoint: str) -> None:
	"""Delete the signed-in user's subscription of *endpoint*. Another user's row is left alone."""
	for name in frappe.get_all(
		SUBSCRIPTION, filters={"endpoint": endpoint, "user": frappe.session.user}, pluck="name"
	):
		frappe.delete_doc(SUBSCRIPTION, name)


def send_push(user: str, title: str, body: str, url: str | None = None) -> int:
	"""Queue one notification to each browser of *user*, and return how many were queued.

	*body* is plain text, cut to 1000 characters and to fit one push message. *url*, opened on a
	click, must be on this site: a path or this site's URL. Nothing is queued while push is off.
	"""
	if url and not is_this_site(url):
		raise ValueError(f"A push notification opens only a page of this site, not {url}")
	if not is_push_on():
		return 0

	payload = get_payload(title, body, url)
	subscriptions = frappe.get_all(SUBSCRIPTION, filters={"user": user}, pluck="name")
	for subscription in subscriptions:
		frappe.enqueue(
			"churchit.church_communications.push.deliver",
			queue="short",
			enqueue_after_commit=True,
			subscription=subscription,
			payload=payload,
		)
	return len(subscriptions)


def get_payload(title: str, body: str, url: str | None) -> str:
	"""The JSON a browser gets, at most MAX_PAYLOAD bytes of UTF-8: a long *body* is cut."""
	body = body[:MAX_BODY]
	while True:
		payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
		excess = len(payload.encode()) - MAX_PAYLOAD
		if excess <= 0:
			return payload
		if not body:
			raise ValueError("A push notification title is too long for one push message")
		body = body.encode()[:-excess].decode(errors="ignore")


def deliver(subscription: str, payload: str) -> None:
	"""Background job: send *payload* to one browser, and delete the subscription its push service forgot."""
	row = frappe.db.get_value(SUBSCRIPTION, subscription, ["endpoint", "p256dh", "auth"], as_dict=True)
	if not row:
		return

	settings = frappe.get_single(SETTINGS)
	try:
		pywebpush.webpush(
			{"endpoint": row.endpoint, "keys": {"p256dh": row.p256dh, "auth": row.auth}},
			payload,
			vapid_private_key=settings.get_password("vapid_private_key"),
			vapid_claims={"sub": settings.vapid_subject},
			ttl=TTL,
			timeout=10,
		)
	except pywebpush.WebPushException as error:
		if error.status_code in GONE:
			frappe.delete_doc(SUBSCRIPTION, subscription, ignore_permissions=True)
			return
		problem = f"The push service answered HTTP {error.status_code}."
	except requests.RequestException as error:
		problem = f"The push service did not answer: {type(error).__name__}."
	else:
		return

	# Logged with a message and outside the except block: a traceback's locals hold the endpoint,
	# its keys and the signed Authorization header.
	frappe.log_error(
		_("Push notification failed"), problem, reference_doctype=SUBSCRIPTION, reference_name=subscription
	)


def delete_user_subscriptions(user, method=None) -> None:
	"""doc_events on_update and on_trash of User: a deleted or disabled user keeps no browser."""
	if method == "on_trash" or not user.enabled:
		frappe.db.delete(SUBSCRIPTION, {"user": user.name})


def is_browser_subscription(subscription) -> bool:
	"""True for an untrusted PushSubscription.toJSON() with a push service endpoint and both keys."""
	if not isinstance(subscription, dict):
		return False

	endpoint, keys = subscription.get("endpoint"), subscription.get("keys")
	if not isinstance(endpoint, str) or not isinstance(keys, dict):
		return False
	return is_push_service(endpoint) and all(
		isinstance(keys.get(key), str) and 0 < len(keys[key]) <= MAX_KEY for key in ("p256dh", "auth")
	)


def is_push_service(endpoint: str) -> bool:
	"""True for an https endpoint of a browser's push service.

	requests (which pywebpush posts with) reads the host with urllib3, so both parsers must name the
	same host, and the endpoint may carry no user, port or other character that could make them differ.
	"""
	parts = urlsplit(endpoint)
	host = parts.hostname or ""
	if parts.scheme != "https" or parts.netloc != host or parse_url(endpoint).host != host:
		return False
	return any(host == service or host.endswith("." + service) for service in PUSH_SERVICES)


def is_this_site(url: str) -> bool:
	"""True for a path on this site or a URL of this site."""
	if "\\" in url:
		return False
	parts = urlsplit(url)
	if not parts.scheme and not parts.netloc:
		return url.startswith("/")
	site = urlsplit(get_url())
	return (parts.scheme, parts.netloc) == (site.scheme, site.netloc)


def has_subscription_permission(doc, ptype=None, user=None) -> bool:
	"""has_permission hook for Push Subscription: a user reaches only their own rows, System Manager all."""
	user = user or frappe.session.user
	return doc.user == user or "System Manager" in frappe.get_roles(user)


def subscription_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions for Push Subscription: a user lists only their own rows."""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return ""
	return f"`tabPush Subscription`.`user` = {frappe.db.escape(user)}"
