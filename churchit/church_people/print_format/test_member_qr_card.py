# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.print_format_generator import get_qr_code

from churchit.church_foundations.doctype.church.church import church_name
from churchit.tests.helpers import ensure_root_church, make_person


class TestMemberQrCard(FrappeTestCase):
	def test_the_card_carries_the_church_the_person_and_a_qr_code_of_their_id(self):
		ensure_root_church()
		person = make_person("Quinn", "_Test Cardholder", photo="/files/quinn.jpg")

		html = frappe.get_print("Person", person.name, "Member QR Card")

		self.assertIn(frappe.utils.escape_html(church_name(person)), html)
		self.assertIn("Quinn _Test Cardholder", html)
		self.assertIn('src="/files/quinn.jpg"', html)
		self.assertIn(f'src="{get_qr_code(person.name)}"', html)

	def test_a_person_without_a_photo_gets_a_card_without_one(self):
		person = make_person("Quill", "_Test Cardholder")

		html = frappe.get_print("Person", person.name, "Member QR Card")

		self.assertNotIn('class="photo"', html)
		self.assertIn(f'src="{get_qr_code(person.name)}"', html)
