# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_foundations.doctype.church.church import get_church
from churchit.tests.helpers import make_address
from churchit.www.contact import get_context


def fresh_church():
	"""The Church loaded outside the document cache, which get_church() shares process-wide.

	Saving the cached copy leaves it holding a timestamp the rolled-back row no
	longer has, and the next save fails as a stale document.
	"""
	return frappe.get_doc("Church", get_church().name)


def contact_settings(**values):
	settings = frappe.get_doc("Contact Us Settings")
	settings.update({"is_disabled": 0, **values})
	settings.save(ignore_permissions=True)


class TestContactPage(FrappeTestCase):
	def setUp(self):
		church = fresh_church()
		church.address = make_address("_Test Church Contact", address_line1="12 Chapel Rd").name
		church.save(ignore_permissions=True)
		contact_settings(
			contact_address_differs=0, address_line1="PO Box 7", city="Elsewhere", phone="555-0100"
		)

	def test_shows_the_church_address_by_default(self):
		context = get_context(frappe._dict())
		self.assertEqual(context["address_title"], get_church().church_name)
		self.assertEqual(context["address_line1"], "12 Chapel Rd")
		self.assertEqual(context["city"], "Springfield")
		self.assertEqual(context["phone"], "555-0100")

	def test_shows_its_own_address_when_told_it_differs(self):
		contact_settings(contact_address_differs=1)
		context = get_context(frappe._dict())
		self.assertEqual(context["address_line1"], "PO Box 7")
		self.assertEqual(context["city"], "Elsewhere")

	def test_leaves_stale_contact_fields_out_when_the_church_has_no_address(self):
		church = fresh_church()
		church.address = None
		church.save(ignore_permissions=True)
		context = get_context(frappe._dict())
		self.assertIsNone(context["address_line1"])
		self.assertIsNone(context["city"])

	def test_every_field_has_a_label(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		set_request(method="GET", path="contact")

		html = get_response("contact").get_data(as_text=True)

		for field in ("subject", "email", "message"):
			self.assertIn(f'<label for="contact-{field}">', html)
			self.assertIn(f'id="contact-{field}"', html)

	def column_heading(self):
		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		set_request(method="GET", path="contact")
		html = get_response("contact").get_data(as_text=True)
		column = html.partition('itemtype="https://schema.org/PostalAddress">')[2]
		return column.partition("</h4>")[0].rpartition(">")[2]

	def test_the_column_names_the_church_unless_the_settings_give_another_address(self):
		self.assertEqual(self.column_heading(), get_church().church_name)

		contact_settings(contact_address_differs=1, address_title=None)
		self.assertEqual(self.column_heading(), "Address")

		contact_settings(contact_address_differs=0)
		church = fresh_church()
		church.address = None
		church.save(ignore_permissions=True)
		self.assertEqual(self.column_heading(), get_church().church_name)
