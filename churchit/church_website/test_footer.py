# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The church details in the website footer."""

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.doctype.church.church import get_church
from churchit.church_website.context import update_website_context
from churchit.church_website.footer import address_line, get_footer_church, map_url
from churchit.tests.helpers import make_address


def set_church_address(address):
	church = get_church()
	church.address = address
	church.founding_date = "1952-06-01"
	church.save(ignore_permissions=True)


class TestFooterChurch(FrappeTestCase):
	def setUp(self):
		address = make_address("_Test Church", address_line1="12 Chapel Rd", state="IL", pincode="62701")
		set_church_address(address.name)
		frappe.db.set_single_value("Contact Us Settings", "phone", "555-0100")

	def test_the_footer_gets_name_address_phone_and_founding_year(self):
		footer = get_footer_church()
		self.assertEqual(footer.name, get_church().church_name)
		self.assertEqual(footer.address, "12 Chapel Rd, Springfield, IL 62701")
		self.assertEqual(footer.phone, "555-0100")
		self.assertEqual(footer.established, "Established 1952")
		self.assertEqual(
			footer.map_url,
			"https://www.openstreetmap.org/search?query=12+Chapel+Rd%2C+Springfield%2C+IL+62701",
		)

	def test_missing_details_are_left_blank_rather_than_invented(self):
		set_church_address(None)
		frappe.db.set_single_value("Contact Us Settings", "phone", None)
		footer = get_footer_church()
		self.assertIsNone(footer.address)
		self.assertIsNone(footer.map_url)
		self.assertFalse(footer.phone)

	def test_address_line_skips_blank_parts(self):
		address = frappe._dict(address_line1="1 Main St", address_line2=None, city="Springfield", state=None)
		self.assertEqual(address_line(address), "1 Main St, Springfield")

	def test_the_context_carries_it_to_every_page(self):
		context = frappe._dict({})
		update_website_context(context)
		self.assertEqual(context.footer_church.phone, "555-0100")

	def test_the_template_puts_identity_left_copyright_centre_contact_right_and_links_below(self):
		html = frappe.render_template(
			"templates/includes/footer/footer.html",
			{
				"footer_church": get_footer_church(),
				"footer_items": [
					{"label": "Submit a Prayer Request", "url": "/prayer-request-anonymous"},
					{"label": "Nested", "url": "/nested", "parent_label": "Submit a Prayer Request"},
				],
				"copyright": "Test Church",
			},
		)
		identity = html[html.index("footer-identity") : html.index("footer-copyright")]
		copyright = html[html.index("footer-copyright") : html.index("footer-contact")]
		contact = html[html.index("footer-contact") : html.index("footer-links")]
		links = html[html.index("footer-links") :]
		self.assertIn(get_church().church_name, identity)
		self.assertIn("Established 1952", identity)
		self.assertIn("&copy; Test Church", copyright)
		self.assertIn('href="tel:555-0100"', contact)
		self.assertIn(
			'href="https://www.openstreetmap.org/search?query=12+Chapel+Rd%2C+Springfield%2C+IL+62701"',
			contact,
		)
		self.assertIn("12 Chapel Rd, Springfield, IL 62701</a>", contact)
		self.assertIn('<a href="/prayer-request-anonymous" class="footer-link"', links)
		self.assertNotIn("/nested", links)

	def test_empty_rows_are_skipped(self):
		html = frappe.render_template(
			"templates/includes/footer/footer.html",
			{"footer_church": None, "footer_items": [], "copyright": None},
		)
		self.assertNotIn("footer-top", html)
		self.assertNotIn("footer-links", html)


class TestRemoveMyAccountFooterLink(FrappeTestCase):
	def test_only_the_shipped_row_is_removed(self):
		from churchit.patches.v1_0.remove_my_account_footer_link import execute

		settings = frappe.get_doc("Website Settings")
		settings.footer_items = []
		settings.append(
			"footer_items", {"label": "Submit a Prayer Request", "url": "/prayer-request-anonymous"}
		)
		settings.append("footer_items", {"label": "My Account", "url": "/me"})
		settings.append("footer_items", {"label": "My Account", "url": "/portal"})
		settings.save(ignore_permissions=True)

		execute()

		rows = [(row.label, row.url) for row in frappe.get_doc("Website Settings").footer_items]
		self.assertEqual(
			rows, [("Submit a Prayer Request", "/prayer-request-anonymous"), ("My Account", "/portal")]
		)
