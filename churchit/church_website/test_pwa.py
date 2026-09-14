# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The site as an installable app: manifest, head tags, service worker, offline page."""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website import pwa
from churchit.church_website.context import update_website_context
from churchit.patches.after_install import DEFAULT_CHURCH_NAME

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

	def test_opens_on_the_portal_in_its_own_window(self):
		manifest = pwa.get_manifest()
		self.assertEqual(manifest["start_url"], "/portal")
		self.assertEqual(manifest["scope"], "/")
		self.assertEqual(manifest["display"], "standalone")

	def test_every_icon_ships_with_the_app(self):
		for icon in pwa.get_manifest()["icons"]:
			self.assertTrue((PUBLIC / icon["src"].removeprefix("/assets/churchit/")).is_file(), icon["src"])
		self.assertIn("maskable", [icon.get("purpose") for icon in pwa.ICONS])

	def test_is_served_as_json_at_the_linked_url(self):
		response, body = serve(pwa.MANIFEST_URL)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "application/json")
		self.assertEqual(json.loads(body)["start_url"], "/portal")


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

	def test_the_offline_page_it_precaches_stands_on_its_own(self):
		response, body = serve("/offline")
		self.assertEqual(response.status_code, 200)
		self.assertIn("You're offline", body)
		self.assertIn(DEFAULT_CHURCH_NAME, body)
		self.assertNotIn("website.bundle", body, "must render with nothing else cached")

	def test_registration_is_included_on_every_web_page(self):
		self.assertIn("/assets/churchit/js/pwa.js", frappe.get_hooks("web_include_js"))
