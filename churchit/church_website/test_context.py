# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The Portal entry in the website's top-right user menu."""

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.context import PORTAL_URL, update_website_context
from churchit.patches.after_install import DEFAULT_CHURCH_NAME


def menu():
	return [{"label": "My Account", "url": "/me"}, {"label": "Log out", "url": "/logout"}]


def labels_for(user):
	frappe.set_user(user)
	context = frappe._dict({"post_login": menu()})
	update_website_context(context)
	return [item["label"] for item in context.post_login]


class TestPortalMenuLink(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_staff_get_a_portal_link(self):
		# The reason this exists: Frappe's own /me Portal link is hidden from
		# System Users, which is what every staff account is.
		self.assertEqual(labels_for("Administrator"), ["Portal", "My Account", "Log out"])

	def test_guests_do_not(self):
		self.assertEqual(labels_for("Guest"), ["My Account", "Log out"])

	def test_link_is_not_added_twice(self):
		frappe.set_user("Administrator")
		context = frappe._dict({"post_login": menu()})
		update_website_context(context)
		update_website_context(context)
		urls = [item["url"] for item in context.post_login]
		self.assertEqual(urls.count(PORTAL_URL), 1)

	def test_a_context_without_a_user_menu_is_left_alone(self):
		frappe.set_user("Administrator")
		context = frappe._dict({})
		update_website_context(context)
		self.assertIsNone(context.get("post_login"))


class TestBrandHtml(FrappeTestCase):
	def test_church_name_fills_the_navbar_brand(self):
		context = frappe._dict({})
		update_website_context(context)
		self.assertEqual(context.brand_html, f"<span>{DEFAULT_CHURCH_NAME}</span>")

	def test_an_admin_set_brand_html_is_left_alone(self):
		# a church that configured its own logo/brand keeps it
		context = frappe._dict({"brand_html": "<img src='/files/logo.png'>"})
		update_website_context(context)
		self.assertEqual(context.brand_html, "<img src='/files/logo.png'>")
