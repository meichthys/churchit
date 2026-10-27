# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.desk.form.load import run_onload
from frappe.handler import execute_cmd
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.utils.global_search import update_global_search
from frappe.website.serve import get_response
from frappe.website.utils import WEBSITE_PAGE_CACHE_PREFIX

from churchit.church_people.membership import MEMBER, VISITOR
from churchit.church_website.published_fields import MEMBERS, PUBLIC, published_field_map
from churchit.tests.helpers import ensure, ensure_user, make_person

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
