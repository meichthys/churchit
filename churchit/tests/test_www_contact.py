# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.doctype.church.church import get_church
from churchit.tests.helpers import make_address
from churchit.www.contact import get_context


def contact_settings(**values):
	settings = frappe.get_doc("Contact Us Settings")
	settings.update({"is_disabled": 0, **values})
	settings.save(ignore_permissions=True)


class TestContactPage(FrappeTestCase):
	def setUp(self):
		church = get_church()
		church.address = make_address("_Test Church Contact", address_line1="12 Chapel Rd").name
		church.save(ignore_permissions=True)
		contact_settings(
			contact_address_differs=0, address_line1="PO Box 7", city="Elsewhere", phone="555-0100"
		)

	def test_shows_the_church_address_by_default(self):
		context = get_context(frappe._dict())
		self.assertEqual(context["address_title"], "_Test Church Contact")
		self.assertEqual(context["address_line1"], "12 Chapel Rd")
		self.assertEqual(context["city"], "Springfield")
		self.assertEqual(context["phone"], "555-0100")

	def test_shows_its_own_address_when_told_it_differs(self):
		contact_settings(contact_address_differs=1)
		context = get_context(frappe._dict())
		self.assertEqual(context["address_line1"], "PO Box 7")
		self.assertEqual(context["city"], "Elsewhere")

	def test_leaves_stale_contact_fields_out_when_the_church_has_no_address(self):
		church = get_church()
		church.address = None
		church.save(ignore_permissions=True)
		context = get_context(frappe._dict())
		self.assertIsNone(context["address_line1"])
		self.assertIsNone(context["city"])
