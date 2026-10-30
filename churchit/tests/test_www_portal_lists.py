# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch
from urllib.parse import urlencode

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.list_renderer import ListPage
from frappe.website.serve import get_response
from frappe.website.utils import WEBSITE_PAGE_CACHE_PREFIX

from churchit.tests.helpers import ensure_user

LANDING = "Member Portal"
PORTAL_CACHE = WEBSITE_PAGE_CACHE_PREFIX + "portal"
# Frappe's Address rows use ERPNext's row template, so the lists are drawn for a member with no addresses.
MEMBER = "_test_portal_lists@example.com"


def serve_portal(user, **form_dict):
	frappe.set_user(user)
	frappe.local.form_dict = frappe._dict(form_dict)
	set_request(method="GET", path="/portal", query_string=urlencode(form_dict))
	return get_response("portal").get_data(as_text=True)


def serve_list(doctype, user):
	"""Render a doctype's portal list the way Frappe does for an app's list route, such as ERPNext's /orders."""
	frappe.set_user(user)
	frappe.local.form_dict = frappe._dict()
	set_request(method="GET", path=f"/{doctype.lower()}")
	return ListPage(doctype).render().get_data(as_text=True)


class TestPortalLists(FrappeTestCase):
	"""churchit's /portal shadows Frappe's portal template, which also draws every app's portal lists."""

	def setUp(self):
		ensure_user(MEMBER, "_Test Portal Lists")
		frappe.cache.delete_value(PORTAL_CACHE)
		self.addCleanup(frappe.cache.delete_value, PORTAL_CACHE)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(setattr, frappe.local, "form_dict", frappe.local.form_dict)

	def test_a_portal_list_route_draws_the_list(self):
		html = serve_list("Address", MEMBER)
		self.assertIn('<h3 class="my-account-header">Addresses</h3>', html)
		self.assertNotIn(LANDING, html)

	def test_portal_itself_stays_the_member_landing(self):
		self.assertIn(LANDING, serve_portal("Administrator"))
		html = serve_portal("Administrator", doctype="Address")
		self.assertIn(LANDING, html)
		self.assertNotIn("my-account-header", html)

	def test_a_cached_landing_never_stands_in_for_a_list(self):
		# force_website_cache would override no_cache, so turn on the cache as production does.
		frappe.local.no_cache = None
		self.addCleanup(setattr, frappe.local, "no_cache", None)
		with patch.dict(frappe.local.conf, {"developer_mode": 0, "disable_website_cache": 0}):
			self.assertIn(LANDING, serve_portal("Guest"))
			self.assertNotIn(LANDING, serve_list("Address", MEMBER))
