# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.menu import get_route


def make_page(route, published=1):
	return frappe.get_doc(
		{"doctype": "Web Page", "title": f"_Test {route}", "route": route, "published": published}
	).insert(ignore_permissions=True)


def menu_urls(table="top_bar_items"):
	return [row.url for row in frappe.get_doc("Website Settings").get(table)]


def alerts():
	return [message for message in frappe.get_message_log() if message.get("alert")]


class TestWebsiteMenu(FrappeTestCase):
	def setUp(self):
		frappe.clear_messages()

	def test_publishing_a_page_adds_it_to_the_end_of_the_menu(self):
		page = make_page("_test-menu-publish", published=0)
		self.assertNotIn("/_test-menu-publish", menu_urls())

		page.published = 1
		page.save()

		last = frappe.get_doc("Website Settings").top_bar_items[-1]
		self.assertEqual((last.label, last.url), ("_Test _test-menu-publish", "/_test-menu-publish"))
		self.assertIn("Added", alerts()[-1].message)

	def test_a_new_published_page_is_added_to_the_menu(self):
		make_page("_test-menu-new")
		self.assertIn("/_test-menu-new", menu_urls())

	def test_a_page_already_on_the_menu_is_not_added_twice(self):
		settings = frappe.get_doc("Website Settings")
		settings.append("top_bar_items", {"label": "Linked", "url": "/_test-menu-linked/"})
		settings.save()

		make_page("_test-menu-linked")
		self.assertEqual(len([url for url in menu_urls() if "_test-menu-linked" in url]), 1)
		self.assertEqual(alerts(), [])

	def test_unpublishing_a_page_removes_its_menu_and_footer_links(self):
		page = make_page("_test-menu-unpublish")
		settings = frappe.get_doc("Website Settings")
		settings.append("footer_items", {"label": "Footer", "url": "/_test-menu-unpublish?x=1"})
		settings.save()
		frappe.clear_messages()

		page.published = 0
		page.save()

		self.assertNotIn("/_test-menu-unpublish", menu_urls())
		self.assertNotIn("/_test-menu-unpublish?x=1", menu_urls("footer_items"))
		self.assertIn("Removed", alerts()[-1].message)

	def test_deleting_a_page_removes_its_menu_links(self):
		page = make_page("_test-menu-delete")
		frappe.clear_messages()

		page.delete()

		self.assertNotIn("/_test-menu-delete", menu_urls())
		self.assertIn("Removed", alerts()[-1].message)

	def test_editing_a_published_page_leaves_the_menu_alone(self):
		page = make_page("_test-menu-edit")
		settings = frappe.get_doc("Website Settings")
		settings.top_bar_items = [row for row in settings.top_bar_items if row.url != "/_test-menu-edit"]
		settings.save()
		frappe.clear_messages()

		page.title = "_Test Renamed"
		page.save()

		self.assertNotIn("/_test-menu-edit", menu_urls())
		self.assertEqual(alerts(), [])

	def test_route_is_read_from_site_relative_links_only(self):
		self.assertEqual(get_route("/sermons/?page=2#top"), "sermons")
		self.assertEqual(get_route("/about/team"), "about/team")
		self.assertIsNone(get_route("https://example.com/sermons"))
		self.assertIsNone(get_route("/"))
		self.assertIsNone(get_route(None))
