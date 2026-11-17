# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The signed unsubscribe link: a GET shows a button, a POST of the same signed link acts."""

from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.verified_command import get_signed_params

from churchit.church_communications.newsletter import is_signed_link, unsubscribe


def click_unsubscribe_link(method: str = "POST", **params) -> None:
	"""Open the link at the foot of a Church Email as a guest, with GET or with the button's POST."""
	frappe.set_user("Guest")
	try:
		with (
			mock.patch.object(frappe.db, "commit"),
			mock.patch.object(
				frappe.local,
				"request",
				SimpleNamespace(method=method, full_path="/api/method/unsubscribe?"),
				create=True,
			),
		):
			unsubscribe(doctype="Church Email", name="x", **params)
	finally:
		frappe.set_user("Administrator")


def request_with(method: str, query_string: str):
	return mock.patch.object(
		frappe.local,
		"request",
		SimpleNamespace(method=method, query_string=query_string.encode()),
		create=True,
	)


class TestSignedLink(FrappeTestCase):
	def test_a_post_with_the_signed_query_string_passes(self):
		query = get_signed_params({"email": "a@example.com", "church": "CHR-01", "purpose": "Church News"})
		with request_with("POST", query):
			self.assertTrue(is_signed_link())

	def test_a_post_with_a_changed_query_string_is_refused(self):
		query = get_signed_params({"email": "a@example.com", "church": "CHR-01"})
		with request_with("POST", query.replace("a%40", "b%40")):
			self.assertFalse(is_signed_link())
		self.assertIn("Invalid Link", frappe.local.message_title)

	def test_a_post_with_no_signature_is_refused(self):
		with request_with("POST", "email=a%40example.com&church=CHR-01"):
			self.assertFalse(is_signed_link())


class TestConfirmButton(FrappeTestCase):
	def test_the_button_of_a_signed_in_member_carries_the_csrf_token(self):
		"""Frappe refuses a signed-in session's POST without its token, so the button must send it."""
		with (
			mock.patch.dict(frappe.session.data, {"csrf_token": "_test_token"}),
			mock.patch.object(
				frappe.local, "request", SimpleNamespace(method="GET", full_path="/x?a=1"), create=True
			),
		):
			unsubscribe(email="a@example.com", church="CHR-01")
		self.assertIn('name="csrf_token" value="_test_token"', frappe.local.message)
