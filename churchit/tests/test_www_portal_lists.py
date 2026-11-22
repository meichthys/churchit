# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.list_renderer import ListPage
from frappe.website.path_resolver import resolve_path
from frappe.website.utils import WEBSITE_PAGE_CACHE_PREFIX

from churchit.tests.helpers import ensure_user

LANDING = '<div class="portal-home">'
PORTAL_CACHE = WEBSITE_PAGE_CACHE_PREFIX + "portal"
# Frappe's Address rows use ERPNext's row template, so the lists are drawn for a member with no addresses.
MEMBER = "_test_portal_lists@example.com"


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
		self.assertIn('<h1 class="my-account-header">Addresses</h1>', html)
		self.assertNotIn(LANDING, html)

	def test_portal_itself_is_the_member_app(self):
		# Frappe's own ?doctype= list never reaches the template there: /portal is the app's page.
		for path, query in (("portal", ""), ("portal", "doctype=Address"), ("portal/household", "")):
			set_request(method="GET", path="/" + path, query_string=query)
			self.assertEqual(resolve_path(path), "member_portal", path)
