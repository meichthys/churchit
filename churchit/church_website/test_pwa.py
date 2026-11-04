# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The site as an installable app: manifest, head tags, service worker, offline page."""

import json
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website import pwa
from churchit.church_website.context import update_website_context
from churchit.patches.after_install import DEFAULT_CHURCH_NAME
from churchit.tests.helpers import RollbackEachTest, ensure_user

PUBLIC = Path(frappe.get_app_path("churchit", "public"))


def serve(path):
	set_request(method="GET", path=path)
	response = get_response(path)
	return response, response.get_data(as_text=True)


class TestManifest(FrappeTestCase):
	def test_names_come_from_the_church(self):
		manifest = pwa.get_manifest()
		self.assertEqual(manifest["name"], DEFAULT_CHURCH_NAME)
		self.assertEqual(manifest["short_name"], "MC")

	def test_opens_through_the_start_route_in_its_own_window(self):
		manifest = pwa.get_manifest()
		self.assertEqual(manifest["start_url"], pwa.START_URL)
		self.assertEqual(manifest["scope"], "/")
		self.assertEqual(manifest["display"], "standalone")

	def test_keeps_the_identity_of_apps_installed_before_the_start_route(self):
		"""Without an id a browser names the app by its start_url, which was /portal."""
		self.assertEqual(pwa.get_manifest()["id"], "/portal")

	def test_shortcuts_leave_out_switched_off_pages(self):
		with patch.object(pwa, "get_switched_off_pages", return_value={"give"}):
			urls = [shortcut["url"] for shortcut in pwa.get_manifest()["shortcuts"]]
		self.assertIn("/calendar", urls)
		self.assertNotIn("/give", urls)

	def test_every_icon_ships_with_the_app(self):
		for icon in pwa.get_manifest()["icons"]:
			self.assertTrue((PUBLIC / icon["src"].removeprefix("/assets/churchit/")).is_file(), icon["src"])
		self.assertIn("maskable", [icon.get("purpose") for icon in pwa.ICONS])
		self.assertTrue((PUBLIC / "icons/pwa/badge-96.png").is_file())

	def test_is_served_as_json_at_the_linked_url(self):
		response, body = serve(pwa.MANIFEST_URL)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "application/json")
		self.assertEqual(json.loads(body)["start_url"], pwa.START_URL)


class TestHeadTags(FrappeTestCase):
	def test_the_tags_are_put_in_the_head_ahead_of_the_theme_script(self):
		context = frappe._dict({})
		update_website_context(context)
		self.assertTrue(context.head_html.startswith(f'<link rel="manifest" href="{pwa.MANIFEST_URL}">'))
		self.assertLess(context.head_html.index("apple-touch-icon"), context.head_html.index("<script>"))

	def test_theme_color_carries_both_palettes_for_the_switch(self):
		self.assertIn(
			'<meta name="theme-color" content="#eef1fb" data-light="#eef1fb" data-dark="#0b1020">',
			pwa.head_tags(),
		)

	def test_ios_gets_the_short_name(self):
		self.assertIn('<meta name="apple-mobile-web-app-title" content="MC">', pwa.head_tags())


class TestServiceWorker(FrappeTestCase):
	def test_is_served_as_a_script_from_the_site_root(self):
		response, body = serve("/sw.js")
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "text/javascript")
		self.assertIn('addEventListener("fetch"', body)

	def test_leaves_api_calls_to_the_browser(self):
		"""Firefox cuts off a navigation its worker waits on for over a minute, such as a large PDF."""
		_response, body = serve("/sw.js")
		self.assertIn('pathname.startsWith("/api/")', body)
		self.assertIn('event.request.mode === "navigate" && !isApiCall', body)

	def test_the_offline_page_it_precaches_stands_on_its_own(self):
		response, body = serve("/offline")
		self.assertEqual(response.status_code, 200)
		self.assertIn("You're offline", body)
		self.assertIn(DEFAULT_CHURCH_NAME, body)
		self.assertNotIn("website.bundle", body, "must render with nothing else cached")

	def test_registration_and_the_install_card_are_on_the_website_and_the_desk(self):
		for scripts, styles in (("web_include_js", "web_include_css"), ("app_include_js", "app_include_css")):
			self.assertIn("/assets/churchit/js/pwa.js", frappe.get_hooks(scripts))
			self.assertIn("/assets/churchit/css/pwa.css", frappe.get_hooks(styles))

	def test_notifications_carry_the_status_bar_badge(self):
		_response, body = serve("/sw.js")
		self.assertIn("badge: BADGE_ICON", body)


class TestInstallOffer(RollbackEachTest):
	def test_is_on_by_default(self):
		self.assertIn('<meta name="churchit-offer-install" content="1">', pwa.install_tags())

	def test_the_church_can_switch_it_off_and_keep_the_app_installable(self):
		frappe.db.set_single_value("Church Features", "offer_app_install", 0)
		tags = pwa.install_tags()
		self.assertNotIn("churchit-offer-install", tags)
		self.assertIn(f'<link rel="manifest" href="{pwa.MANIFEST_URL}">', tags)

	def test_the_desk_boot_carries_the_install_tags_without_the_website_theme_color(self):
		bootinfo = frappe._dict()
		pwa.extend_bootinfo(bootinfo)
		self.assertEqual(bootinfo.pwa_install_tags, pwa.install_tags())
		self.assertNotIn("theme-color", bootinfo.pwa_install_tags)

	def test_names_the_app_for_the_install_card(self):
		self.assertIn(f'<meta name="application-name" content="{DEFAULT_CHURCH_NAME}">', pwa.install_tags())


class TestAppStart(RollbackEachTest):
	def location(self, user):
		frappe.set_user(user)
		response, _body = serve(pwa.START_URL)
		self.assertEqual(
			response.status_code, 302, "a browser keeps a 301, but the answer depends on the user"
		)
		return response.headers["Location"]

	def test_opens_the_desk_for_staff(self):
		self.assertTrue(self.location("Administrator").endswith(pwa.DESK_URL))

	def test_opens_the_portal_for_members(self):
		member = ensure_user("_test_app_member@example.com", "App Member")
		self.assertTrue(self.location(member).endswith(pwa.PORTAL_URL))

	def test_sends_a_guest_to_log_in_and_back(self):
		self.assertTrue(self.location("Guest").endswith("/login?redirect-to=/app-start"))
