# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import set_request
from frappe.website.path_resolver import resolve_path

from churchit.church_scope import root_church
from churchit.church_website.pages import sync_page_switches
from churchit.portal import access, realtime
from churchit.portal.boot import get_boot
from churchit.portal.nav import APP_PAGES, get_menu
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, ensure_user, make_person
from churchit.www import member_portal

MEMBER = "portal-boot-member@example.com"
NO_PERSON = "portal-boot-no-person@example.com"


def switch_page(route, enabled):
	features = frappe.get_single("Church Features")
	features.get("website_pages", {"route": route})[0].enabled = enabled
	features.save()


class TestMemberPortalPage(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_root_church()
		sync_page_switches()
		ensure_user(MEMBER, "Boot")
		ensure_user(NO_PERSON, "Nobody")
		cls.person = (
			frappe.db.get_value("Person", {"user": MEMBER}) or make_person("Boot", "Member", user=MEMBER).name
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.request = None
		super().tearDown()

	def test_every_portal_path_opens_the_app(self):
		for path in ("portal", "portal/household", "portal/groups/GRP-0001/edit"):
			set_request(method="GET", path="/" + path)
			self.assertEqual(resolve_path(path), "member_portal", path)

	def test_a_guest_goes_to_login_and_comes_back_to_the_same_path(self):
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(path="/portal/household", query_string=b"tab=check-in")

		with self.assertRaises(frappe.Redirect) as raised:
			member_portal.get_context(frappe._dict())

		self.assertEqual(raised.exception.http_status_code, 302)
		self.assertEqual(
			frappe.local.flags.redirect_location, "/login?redirect-to=/portal/household%3Ftab%3Dcheck-in"
		)

	def test_the_page_never_enters_the_page_cache(self):
		self.assertEqual(member_portal.no_cache, 1)
		frappe.set_user(MEMBER)
		context = frappe._dict()

		member_portal.get_context(context)

		self.assertEqual(context.no_cache, 1)

	def test_the_boot_names_the_member_and_their_church(self):
		frappe.set_user(MEMBER)

		boot = get_boot()

		self.assertTrue(boot["csrf_token"])
		app = boot["churchit"]
		self.assertEqual(app["person"], self.person)
		self.assertEqual(app["user"]["name"], MEMBER)
		self.assertFalse(app["user"]["is_staff"])
		church = frappe.db.get_value("Person", self.person, "church") or root_church()
		self.assertEqual(app["church"]["name"], church)
		self.assertEqual(frappe.as_json(boot), frappe.as_json(frappe.parse_json(frappe.as_json(boot))))

	def test_a_login_with_no_person_still_opens_the_app(self):
		frappe.set_user(NO_PERSON)

		app = get_boot()["churchit"]

		self.assertIsNone(app["person"])
		self.assertTrue(app["church"])

	def test_the_menu_drops_a_switched_off_page_and_gets_it_back(self):
		frappe.set_user(MEMBER)
		self.assertIn("bulletins", menu_pages())

		frappe.set_user("Administrator")
		switch_page("bulletins", 0)
		frappe.set_user(MEMBER)
		self.assertNotIn("bulletins", menu_pages())
		self.assertIn("bulletins", get_menu()["hidden_pages"])

		frappe.set_user("Administrator")
		switch_page("bulletins", 1)
		frappe.set_user(MEMBER)
		self.assertIn("bulletins", menu_pages())

	def test_app_pages_open_in_the_app_and_other_rows_stay_links(self):
		frappe.set_user(MEMBER)

		links = [link for section in get_menu()["navigation"] for link in section["links"]]

		for link in links:
			self.assertEqual(link["app"], link["page"] in APP_PAGES, link)
			self.assertEqual(link["href"] is None, link["app"], link)

	def test_a_website_link_to_a_switched_off_page_goes(self):
		frappe.set_user("Administrator")
		switch_page("calendar", 0)
		frappe.set_user(MEMBER)

		self.assertNotIn("calendar", [link["page"] for link in get_menu()["site_links"]])


class TestPortalAccess(RollbackEachTest):
	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_a_guest_and_a_login_with_no_person_are_refused(self):
		ensure_user(NO_PERSON, "Nobody")
		for user in ("Guest", NO_PERSON):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				access.require_person()

	def test_a_switched_off_page_is_refused(self):
		sync_page_switches()
		access.require_page("bulletins")

		switch_page("bulletins", 0)

		with self.assertRaises(frappe.PermissionError):
			access.require_page("bulletins")

	def test_a_hint_goes_to_the_user_after_the_commit_and_never_to_a_guest(self):
		with patch("churchit.portal.realtime.frappe.publish_realtime") as publish:
			realtime.notify("Guest", "sign-ups")
			realtime.notify(None, "sign-ups")
			realtime.notify(MEMBER, "sign-ups", "SU-0001")

		publish.assert_called_once_with(
			realtime.EVENT, {"topic": "sign-ups", "name": "SU-0001"}, user=MEMBER, after_commit=True
		)


def menu_pages():
	return [link["page"] for section in get_menu()["navigation"] for link in section["links"]]
