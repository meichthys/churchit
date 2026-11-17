# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The sections of the member portal home page."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website.portal_home import get_portal_home_sections


def routes_of(section):
	return [link.route for link in section.links]


class TestPortalHomeSections(FrappeTestCase):
	def test_every_shipped_portal_row_has_a_section_and_a_line(self):
		menu = frappe.get_single("Portal Settings").menu
		items = [{"title": row.title, "route": row.route} for row in menu if row.role == "Church User"]
		self.assertTrue(items)

		sections = get_portal_home_sections(items)

		self.assertNotIn("More", [section.title for section in sections])
		for section in sections:
			for link in section.links:
				self.assertTrue(link.description, link.route)

	def test_unknown_rows_go_last_in_menu_order(self):
		items = [
			{"title": "Our Camp", "route": "/camp"},
			{"title": "Bible", "route": "/bible"},
			{"title": "Choir", "route": "choir"},
		]

		sections = get_portal_home_sections(items)

		self.assertEqual([section.title for section in sections], ["Bible and Bulletins", "More"])
		self.assertEqual(routes_of(sections[0]), ["/bible"])
		self.assertEqual(sections[0].links[0].icon, "book-open")
		self.assertEqual(routes_of(sections[1]), ["/camp", "choir"])

	def test_a_section_keeps_its_own_order(self):
		items = [{"title": "Group Files", "route": "group-files"}, {"title": "Groups", "route": "groups"}]

		(section,) = get_portal_home_sections(items)

		self.assertEqual(routes_of(section), ["groups", "group-files"])


class TestGuestPortal(FrappeTestCase):
	def test_a_guest_is_offered_the_connection_card(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		set_request(method="GET", path="portal")

		html = get_response("portal").get_data(as_text=True)

		self.assertIn('<a href="/connection-card/new">Fill in a Connection Card</a>', html)
		self.assertIn('Ask <a href="/contact">the church office</a> to invite you.', html)
