# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.desk.form.load import run_onload
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.utils.global_search import update_global_search
from frappe.website.doctype.web_form.web_form import accept
from frappe.website.doctype.website_settings.website_settings import modify_header_footer_items
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response
from frappe.website.utils import WEBSITE_PAGE_CACHE_PREFIX, clear_website_cache

from churchit.church_people.membership import MEMBER, VISITOR
from churchit.church_setup.doctype.church_features.church_features import MODULE_FIELDS
from churchit.church_website.context import update_website_context
from churchit.church_website.pages import SwitchedOffPage, is_link_off, is_page_off, sync_page_switches
from churchit.church_website.published_fields import MEMBERS, PUBLIC, published_field_map
from churchit.patches.after_install import read_template
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, force_single_church, make_person

MEMBERS_ROUTE = "_test-members-only"
SECRET = "_Test words for members"


def serve(path, user):
	frappe.set_user(user)
	frappe.local.form_dict = frappe._dict()
	set_request(method="GET", path=path)
	return get_response(path)


def make_web_page(title, **values):
	return frappe.get_doc(
		{"doctype": "Web Page", "title": title, "published": 1, "content_type": "Rich Text", **values}
	).insert(ignore_permissions=True)


class TestMembersOnlyPage(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for membership in (MEMBER, VISITOR):
			ensure("Membership Type", {"type": membership})
		cls.page = make_web_page(
			"_Test Members Only", route=MEMBERS_ROUTE, members_only=1, main_section=f"<p>{SECRET}</p>"
		)
		cls.public_page = make_web_page(
			"_Test Open Page", route="_test-open-page", main_section="<p>Open</p>"
		)
		cls.member = ensure_user("_test_members_only_member@example.com", "Member")
		make_person("_Test Gate", "Member", user=cls.member, membership=MEMBER)
		cls.visitor = ensure_user("_test_members_only_visitor@example.com", "Visitor")
		make_person("_Test Gate", "Visitor", user=cls.visitor, membership=VISITOR)
		cls.stranger = ensure_user("_test_members_only_stranger@example.com", "Stranger")

	def setUp(self):
		frappe.flags.force_website_cache = True

	def tearDown(self):
		frappe.flags.force_website_cache = False
		frappe.cache.delete_value(WEBSITE_PAGE_CACHE_PREFIX + MEMBERS_ROUTE)
		frappe.set_user("Administrator")

	def test_a_guest_never_gets_the_page_a_member_cached(self):
		response = serve(MEMBERS_ROUTE, self.member)
		self.assertEqual(response.status_code, 200)
		self.assertIn(SECRET, response.get_data(as_text=True))
		self.assertTrue(frappe.cache.get_value(WEBSITE_PAGE_CACHE_PREFIX + MEMBERS_ROUTE))

		response = serve(MEMBERS_ROUTE, "Guest")
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers["Location"], f"/login?redirect-to=/{MEMBERS_ROUTE}")
		self.assertNotIn(SECRET, response.get_data(as_text=True))

	def test_a_guest_is_sent_to_login_at_any_case_or_accent(self):
		for path in (MEMBERS_ROUTE.upper(), MEMBERS_ROUTE.replace("e", "é")):
			response = serve(path, "Guest")
			self.assertEqual(response.status_code, 301, path)
			self.assertTrue(response.headers["Location"].startswith("/login?"), path)
			self.assertNotIn(SECRET, response.get_data(as_text=True), path)

	def test_a_user_with_no_person_is_refused(self):
		response = serve(MEMBERS_ROUTE, self.stranger)
		self.assertEqual(response.status_code, 403)
		self.assertNotIn(SECRET, response.get_data(as_text=True))

	def test_a_visitor_is_refused(self):
		response = serve(MEMBERS_ROUTE, self.visitor)
		self.assertEqual(response.status_code, 403)
		self.assertNotIn(SECRET, response.get_data(as_text=True))

	def test_a_web_page_editor_without_a_person_can_open_it(self):
		response = serve(MEMBERS_ROUTE, "Administrator")
		self.assertEqual(response.status_code, 200)
		self.assertIn(SECRET, response.get_data(as_text=True))

	def test_a_public_page_still_serves_guests(self):
		self.assertEqual(serve("_test-open-page", "Guest").status_code, 200)

	def test_guest_search_never_returns_a_members_only_page(self):
		# Read the queued values: __global_search is MyISAM, so rows written here outlive the rollback.
		with patch("frappe.utils.global_search.sync_value_in_queue") as queue:
			for page in (self.page, self.public_page):
				update_global_search(page)

		published = {call.args[0]["name"]: call.args[0]["published"] for call in queue.call_args_list}
		self.assertEqual(published, {self.page.name: 0, self.public_page.name: 1})

	def test_a_dynamic_route_members_only_page_is_kept_from_guests(self):
		make_web_page(
			"_Test Members Dynamic",
			route="_test-members-dynamic/<item>",
			dynamic_route=1,
			members_only=1,
			main_section=f"<p>{SECRET}</p>",
		)

		response = serve("_test-members-dynamic/1", "Guest")
		self.assertEqual(response.status_code, 301)
		self.assertEqual(response.headers["Location"], "/login?redirect-to=/_test-members-dynamic/1")
		self.assertNotIn(SECRET, response.get_data(as_text=True))

		self.assertEqual(serve("_test-members-dynamic/1", self.stranger).status_code, 403)
		self.assertIn(SECRET, serve("_test-members-dynamic/1", self.member).get_data(as_text=True))

	def test_the_portal_list_api_hides_a_members_only_page_from_a_non_member(self):
		def list_pages(user):
			frappe.set_user(user)
			frappe.local.form_dict = frappe._dict(doctype="Web Page", txt="_Test")
			set_request(method="GET", path="/api/method/frappe.www.list.get_list_data")
			return [row.name for row in execute_cmd("frappe.www.list.get_list_data")]

		self.assertNotIn(self.page.name, list_pages(self.stranger))
		self.assertIn(self.public_page.name, list_pages(self.stranger))
		self.assertIn(self.page.name, list_pages(self.member))

	def test_a_members_only_page_still_gets_a_route_and_a_desk_link(self):
		page = make_web_page("_Test Members Routed", members_only=1)
		self.assertEqual(page.route, page.scrubbed_title())

		run_onload(page)
		self.assertTrue(page.get_onload().published)

	def test_its_fields_get_the_members_only_badge(self):
		make_web_page(
			"_Test Members Fields",
			route="_test-members-fields",
			members_only=1,
			dynamic_template=1,
			content_type="HTML",
			main_section_html='{% for p in frappe.get_list("Person", fields=["nickname"]) %}{{ p.nickname }}{% endfor %}',
		)

		sources = published_field_map()["Person"]["nickname"]
		self.assertIn(
			{"title": "_Test Members Fields", "route": "_test-members-fields", "access": MEMBERS}, sources
		)
		self.assertNotIn(
			{"title": "_Test Members Fields", "route": "_test-members-fields", "access": PUBLIC}, sources
		)


def resolve(path):
	set_request(method="GET", path=path)
	return PathResolver(path).resolve()[1]


class TestSwitchedOffPage(RollbackEachTest):
	def setUp(self):
		super().setUp()
		sync_page_switches()
		features = frappe.get_single("Church Features")
		for field in MODULE_FIELDS:
			features.set(field, 1)
		for row in features.website_pages:
			row.enabled = 1
		features.save()
		frappe.flags.force_website_cache = True
		self.addCleanup(clear_website_cache)
		self.addCleanup(setattr, frappe.flags, "force_website_cache", False)

	def switch(self, route, enabled):
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": route})[0].enabled = enabled
		features.save()

	def set_module(self, field, enabled):
		features = frappe.get_single("Church Features")
		features.set(field, enabled)
		features.save()

	def test_a_page_switched_off_is_not_found_until_it_is_on_again(self):
		self.assertEqual(serve("bulletins", "Administrator").status_code, 200)

		self.switch("bulletins", 0)
		self.assertEqual(serve("bulletins", "Administrator").status_code, 404)
		self.assertEqual(serve("bulletins/anything", "Administrator").status_code, 404)

		self.switch("bulletins", 1)
		self.assertEqual(serve("bulletins", "Administrator").status_code, 200)

	def test_the_portal_drops_its_link_and_gets_it_back(self):
		self.assertIn('href="/bulletins"', serve("portal", "Administrator").get_data(as_text=True))

		self.switch("bulletins", 0)
		self.assertNotIn('href="/bulletins"', serve("portal", "Administrator").get_data(as_text=True))

		self.switch("bulletins", 1)
		self.assertIn('href="/bulletins"', serve("portal", "Administrator").get_data(as_text=True))

	def test_navbar_and_footer_links_go_and_the_cached_rows_stay(self):
		settings = frappe.get_doc("Website Settings")
		settings.set("top_bar_items", [])
		settings.set("footer_items", [])
		settings.append("top_bar_items", {"label": "_Test News", "url": "/bulletins"})
		settings.append("top_bar_items", {"label": "_Test More"})
		for label, url in (("_Test Sheet", "/bulletins?x=1"), ("_Test About", "/about")):
			settings.append("top_bar_items", {"label": label, "url": url, "parent_label": "_Test More"})
		settings.append("footer_items", {"label": "_Test Footer News", "url": "/bulletins"})
		cached = modify_header_footer_items(settings.top_bar_items)
		more = cached[1]
		self.switch("bulletins", 0)

		context = frappe._dict(
			top_bar_items=list(cached),
			footer_items=modify_header_footer_items(settings.footer_items),
			sidebar_items=[{"route": "bulletins"}, {"route": "/about"}],
			web_include_js=[],
			web_include_css=[],
		)
		update_website_context(context)

		self.assertEqual(
			[item.label for item in context.top_bar_items if item.label.startswith("_Test")],
			["_Test More", "_Test About"],
		)
		new_more = next(item for item in context.top_bar_items if item.label == "_Test More")
		self.assertEqual([child.label for child in new_more.child_items], ["_Test About"])
		self.assertEqual(len(more.child_items), 2)
		self.assertEqual(context.footer_items, [])
		self.assertEqual(context.sidebar_items, [{"route": "/about"}])

	def test_a_module_switched_off_takes_its_pages_with_it(self):
		self.set_module("enable_study", 0)

		for path in ("sermons", "sermon/_test-sermon", "podcast.xml", "memorize/session"):
			self.assertIsInstance(resolve(path), SwitchedOffPage, path)
		self.assertEqual(serve("sermons", "Guest").status_code, 404)
		for path in ("live", "bulletins", "about"):
			self.assertNotIsInstance(resolve(path), SwitchedOffPage, path)

	def test_a_sermon_page_links_back_only_to_a_sermons_page_that_is_on(self):
		sermon = frappe.get_doc({"doctype": "Sermon", "title": "_Test Back Link", "publish": 1}).insert()
		path = f"sermon/{sermon.name}"
		self.assertIn('class="sermon-back"', serve(path, "Guest").get_data(as_text=True))

		frappe.set_user("Administrator")
		self.switch("sermons", 0)
		response = serve(path, "Guest")
		self.assertEqual(response.status_code, 200)
		self.assertNotIn('class="sermon-back"', response.get_data(as_text=True))

	def test_the_sermons_page_links_only_to_pages_that_are_on(self):
		force_single_church()
		frappe.db.set_value("Web Page", "sermons", "main_section_html", read_template("sermons.html"))
		series = frappe.get_doc(
			{"doctype": "Sermon Series", "series_name": "_Test Off Series", "publish": 1}
		).insert()
		sermons = [
			frappe.get_doc({"doctype": "Sermon", "title": "_Test Off Card", "publish": 1}).insert(),
			frappe.get_doc(
				{"doctype": "Sermon", "title": "_Test Off Series Sermon", "publish": 1, "series": series.name}
			).insert(),
		]
		links = [
			f'href="/{page}{sermon.name}'
			for sermon in sermons
			for page in ("sermon/", "sermon_presentation?name=")
		]
		html = serve("sermons", "Guest").get_data(as_text=True)
		for link in links:
			self.assertIn(link, html)

		frappe.set_user("Administrator")
		self.switch("sermon", 0)
		self.switch("sermon_presentation", 0)
		html = serve("sermons", "Guest").get_data(as_text=True)
		for link in links:
			self.assertNotIn(link, html)
		self.assertIn("_Test Off Series Sermon", html)

	def test_a_switch_matches_whole_route_segments(self):
		self.assertTrue(is_page_off("/prayer-request/new", {"prayer-request"}))
		self.assertFalse(is_page_off("prayer-request-anonymous", {"prayer-request"}))
		self.assertFalse(is_page_off("sermon_presentation", {"sermon"}))
		self.assertFalse(is_page_off("", {"sermon"}))

	def test_a_web_page_is_off_at_any_case_or_accent(self):
		# MariaDB finds the shipped "sermons" Web Page for each of these paths.
		paths = ("Sermons", "SERMONS", "Sermons.html", "sérmons")
		for path in paths:
			self.assertEqual(serve(path, "Guest").status_code, 200, path)

		frappe.set_user("Administrator")
		self.set_module("enable_study", 0)
		for path in paths:
			self.assertEqual(serve(path, "Guest").status_code, 404, path)
		self.assertTrue(is_page_off("SERMONS", {"sermons"}))
		self.assertTrue(is_link_off("/Sermons", {"sermons"}))

	def test_a_switched_off_web_form_takes_no_submission(self):
		form = "prayer-request-anonymous"
		request_type = ensure("Prayer Request Type", {"type": "Health"})
		data = {
			"title": "_Test Off",
			"type": request_type,
			"visibility": "Whole Church",
			"request": "_Test Off",
		}
		frappe.local.request = None  # an earlier test's request would turn on the rate limit
		frappe.set_user("Guest")
		self.assertEqual(accept(form, frappe.as_json(data)).owner, "Guest")

		frappe.set_user("Administrator")
		self.switch(form, 0)
		before = frappe.db.count("Prayer Request")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			accept(form, frappe.as_json(data))
		self.assertEqual(frappe.db.count("Prayer Request"), before)
