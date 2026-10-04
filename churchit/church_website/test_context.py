# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the website context hook adds to every page."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response
from frappe.website.utils import get_portal_sidebar_items

from churchit.church_website.context import PORTAL_URL, update_website_context
from churchit.patches.after_install import DEFAULT_CHURCH_NAME
from churchit.tests.helpers import ensure_user


def menu():
	return [{"label": "My Account", "url": "/me"}, {"label": "Log out", "url": "/logout"}]


def serve(path):
	"""Render *path*, following a web form's redirect to its list."""
	frappe.local.form_dict = frappe._dict()
	set_request(method="GET", path=path)
	response = get_response(path)
	if response.status_code in (301, 302):
		return serve(response.headers["Location"].lstrip("/"))
	return response.get_data(as_text=True)


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


class TestPortalSidebar(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def test_every_portal_page_shows_the_whole_menu(self):
		# A web form fills its sidebar from a Website Sidebar record alone, and a
		# www page shows one only when it asks to, so either could drop the menu.
		frappe.set_user(ensure_user("_test_sidebar_member@example.com", "_Test Sidebar Member"))
		menu = get_portal_sidebar_items()
		self.assertTrue(menu)
		for item in menu:
			with self.subTest(route=item.route):
				html = serve(item.route)
				self.assertIn('class="web-sidebar"', html)
				for link in menu:
					self.assertIn(f'href="/{link.route.lstrip("/")}"', html)

	def test_relative_routes_are_made_absolute(self):
		# "bible" seen from /prayer-request/new would be /prayer-request/bible
		context = frappe._dict(
			show_sidebar=1,
			sidebar_items=[
				{"title": "Bible", "route": "bible"},
				{"title": "My Account", "route": "/me"},
				{"title": "Elsewhere", "route": "https://example.com/give"},
			],
		)
		update_website_context(context)
		self.assertEqual(
			[item["route"] for item in context.sidebar_items],
			["/bible", "/me", "https://example.com/give"],
		)

	def test_a_page_without_a_sidebar_is_left_alone(self):
		context = frappe._dict()
		update_website_context(context)
		self.assertIsNone(context.get("sidebar_items"))


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


class TestThemeModeScript(FrappeTestCase):
	def test_the_script_is_put_in_the_head(self):
		context = frappe._dict({})
		update_website_context(context)
		self.assertTrue(context.head_html.endswith("</script>"))
		self.assertIn("churchit-theme-mode", context.head_html)

	def test_a_church_set_head_html_stays_in_front_of_it(self):
		context = frappe._dict({"head_html": '<meta name="x" content="y">'})
		update_website_context(context)
		self.assertTrue(context.head_html.startswith('<meta name="x" content="y"><link rel="manifest"'))


class TestNavbarSwitch(FrappeTestCase):
	def test_the_switch_renders_left_of_the_account_menu(self):
		html = frappe.render_template(
			"templates/includes/navbar/navbar_login.html", {"post_login": [], "hide_login": False}
		)
		self.assertLess(
			html.index("theme-switch"), html.index("btn-login-area"), "frappe's own block follows"
		)
		self.assertIn("#icon-moon", html)
