# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the website context hook adds to every page."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response
from frappe.website.utils import get_portal_sidebar_items

from churchit.church_finances.doctype.giving_settings.giving_settings import GivingSettings
from churchit.church_website.context import PORTAL_URL, update_website_context
from churchit.patches.after_install import DEFAULT_CHURCH_NAME
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_branch,
	make_person,
	serve_old_member_pages,
	set_multi_church,
)


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
		self.assertEqual(labels_for("Administrator"), ["Member Portal", "My Account", "Log out"])

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
	def setUp(self):
		super().setUp()
		serve_old_member_pages(self)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def test_every_portal_page_shows_the_whole_menu(self):
		# A web form fills its sidebar from a Website Sidebar record alone, and a
		# www page shows one only when it asks to, so either could drop the menu.
		frappe.set_user(ensure_user("_test_sidebar_member@example.com", "_Test Sidebar Member"))
		menu = get_portal_sidebar_items()
		self.assertTrue(menu)
		# Lead a Group shows only to a group leader.
		shown = [link for link in menu if link.route.strip("/") != "group-leader"]
		for item in menu:
			with self.subTest(route=item.route):
				html = serve(item.route)
				self.assertIn('class="web-sidebar"', html)
				for link in shown:
					self.assertIn(f'href="/{link.route.lstrip("/")}"', html)
				self.assertNotIn('href="/group-leader"', html)

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
			[PORTAL_URL, "/bible", "/me", "https://example.com/give"],
		)

	def test_the_menu_starts_at_the_portal_home_for_a_signed_in_visitor(self):
		def routes(**context):
			context = frappe._dict(
				show_sidebar=1, sidebar_items=[{"title": "Bible", "route": "/bible"}], **context
			)
			update_website_context(context)
			return [item["route"] for item in context.sidebar_items]

		self.assertEqual(routes(), [PORTAL_URL, "/bible"])
		self.assertEqual(routes(website_sidebar="_Test Own Sidebar"), ["/bible"], "a page's own menu stays")
		self.assertEqual(routes(web_form_doc={"website_sidebar": "_Test Own Sidebar"}), ["/bible"])

		frappe.set_user("Guest")
		self.assertEqual(routes(), ["/bible"])

	def test_a_page_without_a_sidebar_is_left_alone(self):
		context = frappe._dict()
		update_website_context(context)
		self.assertIsNone(context.get("sidebar_items"))


class TestFileRoutes(FrappeTestCase):
	def test_a_file_gets_no_menu_or_head_tags(self):
		for path in ("sw.js", "website_script.js", "manifest.json"):
			context = frappe._dict(path=path, post_login=menu(), show_sidebar=1)
			update_website_context(context)
			self.assertEqual(context, frappe._dict(path=path, post_login=menu(), show_sidebar=1), path)

	def test_a_page_whose_route_holds_a_dot_still_gets_them(self):
		context = frappe._dict(path="sermon/john-3.16", post_login=menu())
		update_website_context(context)
		self.assertEqual(context.post_login[0]["url"], PORTAL_URL)
		self.assertIn("head_html", context)


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

	def test_the_phone_menu_names_the_switch(self):
		html = frappe.render_template(
			"templates/includes/navbar/navbar_login.html", {"post_login": [], "hide_login": False}
		)
		self.assertIn('<span class="theme-switch-moon d-xl-none">Dark mode</span>', html)
		self.assertIn('<span class="theme-switch-sun d-xl-none">Light mode</span>', html)

	def test_the_links_go_into_the_menu_button_below_1200px(self):
		html = frappe.render_template("templates/includes/navbar/navbar.html", {"top_bar_items": []})
		self.assertIn('<nav class="navbar navbar-light navbar-expand-xl">', html)
		self.assertNotIn("navbar-expand-lg", html)
		self.assertIn('id="navbarSupportedContent"', html, "the rest is frappe's own template")


class TestLeafletOnMissions(FrappeTestCase):
	def context_for(self, path):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.local.path = path
		hooks = frappe.get_hooks()
		context = frappe._dict(web_include_js=hooks.web_include_js, web_include_css=hooks.web_include_css)
		update_website_context(context)
		return context

	def test_missions_loads_leaflet_before_its_map_script(self):
		context = self.context_for("missions")
		update_website_context(context)

		scripts = context.web_include_js
		self.assertEqual(scripts.count("leaflet.bundle.js"), 1)
		self.assertLess(
			scripts.index("leaflet.bundle.js"), scripts.index("/assets/churchit/js/missions_map.js")
		)
		self.assertEqual(context.web_include_css.count("leaflet.bundle.css"), 1)
		self.assertNotIn("leaflet.bundle.js", frappe.get_hooks("web_include_js"))

	def test_the_calendar_loads_leaflet_for_its_event_map(self):
		context = self.context_for("calendar")
		self.assertEqual(context.web_include_js.count("leaflet.bundle.js"), 1)
		self.assertEqual(context.web_include_css.count("leaflet.bundle.css"), 1)

	def test_other_pages_do_not_load_leaflet(self):
		self.assertNotIn("leaflet.bundle.js", self.context_for("about").web_include_js)


class TestMultiChurchNavbar(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		set_multi_church(True)
		cls.branch = make_branch("_Test Navbar Branch", "TNB", publish=1)
		frappe.db.set_value("Church", cls.root, "publish", 1)
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def navbar(self, church=None, **values):
		frappe.local.form_dict = frappe._dict(church=church) if church else frappe._dict()
		context = frappe._dict(
			top_bar_items=[
				frappe._dict(label="Home", url="/home", right=1),
				frappe._dict(label="Sermons", url="/sermons", right=1),
			],
			**values,
		)
		update_website_context(context)
		return context

	def test_the_locations_menu_sits_beside_home_and_marks_the_shown_church(self):
		items = self.navbar(self.branch).top_bar_items

		self.assertEqual([item.label for item in items], ["Home", "Sermons", "Locations"])
		labels = [child.label for child in items[-1].child_items]
		self.assertIn("_Test Navbar Branch (selected)", labels)
		self.assertNotIn("_Test Navbar Branch", labels)

	def test_the_body_class_tells_website_css_that_the_bar_holds_locations(self):
		self.assertEqual(self.navbar().body_class, "has-locations-menu")
		self.assertEqual(self.navbar(body_class="my-page").body_class, "my-page has-locations-menu")

	def test_the_menu_rows_of_website_settings_are_left_as_they_are(self):
		context = frappe._dict(top_bar_items=[frappe._dict(label="Home", url="/home", right=1)])
		rows = context.top_bar_items
		update_website_context(context)
		self.assertEqual([row.label for row in rows], ["Home"])

	def test_a_member_page_names_the_member_s_own_church(self):
		user = ensure_user("_test_navbar_member@example.com", "Navbar")
		make_person("_Test Navbar", "Member", church=self.branch, user=user)
		frappe.set_user(user)
		frappe.local.form_dict = frappe._dict(church=self.root)

		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		titles = {}
		for path in ("directory", "community-prayer-requests/list", "sermons"):
			frappe.local.path = path
			context = frappe._dict(title="_Test Title")
			update_website_context(context)
			titles[path] = context.title

		self.assertEqual(titles["directory"], "_Test Title: _Test Navbar Branch")
		self.assertEqual(titles["community-prayer-requests/list"], "_Test Title: _Test Navbar Branch")
		self.assertEqual(titles["sermons"], "_Test Title")

	def test_a_single_church_site_keeps_the_plain_title_and_its_home_link(self):
		force_single_church()
		user = ensure_user("_test_navbar_single@example.com", "Single")
		make_person("_Test Navbar", "Single", church=self.root, user=user)
		frappe.set_user(user)

		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.local.path = "directory"
		context = frappe._dict(title="_Test Title", top_bar_items=[frappe._dict(label="Home", url="/home")])
		update_website_context(context)

		self.assertEqual(context.title, "_Test Title")
		self.assertEqual([item.label for item in context.top_bar_items], ["Home"])
		self.assertIsNone(context.body_class)


class TestGiveLink(RollbackEachTest):
	def give_links(self):
		"""How many navbar and footer links point at /give."""
		context = frappe._dict(
			top_bar_items=[
				frappe._dict(label="Give", url="/give"),
				frappe._dict(label="Sermons", url="/sermons"),
			],
			footer_items=[frappe._dict(label="Give", url="/give")],
		)
		update_website_context(context)
		return [item.get("url") for item in context.top_bar_items + context.footer_items].count("/give")

	def test_the_give_link_shows_only_while_giving_online_is_on(self):
		with patch.object(GivingSettings, "get_offered_gateways", return_value=[{"name": "_Test"}]):
			frappe.db.set_single_value("Giving Settings", "enabled", 0)
			self.assertEqual(self.give_links(), 0)

			frappe.db.set_single_value("Giving Settings", "enabled", 1)
			self.assertEqual(self.give_links(), 2)

		with patch.object(GivingSettings, "get_offered_gateways", return_value=[]):
			self.assertEqual(self.give_links(), 0)
