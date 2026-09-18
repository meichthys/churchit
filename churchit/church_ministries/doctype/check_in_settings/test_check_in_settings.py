# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import MagicMock, patch

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.doctype.function_check_in.function_check_in import print_name_tags
from churchit.tests.helpers import make_function, make_person


class TestCheckInSettings(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.function = make_function("_Test Tag Function", start_date="2031-05-01")
		cls.person = make_person("Bartholomew-Alexander", "Featherstonehaugh")

	def setUp(self):
		self.settings = frappe.get_single("Check-In Settings")
		self.settings.update(
			{
				"name_tag_printing": "Browser",
				"label_width": 4,
				"label_height": 2,
				"label_dpi": "203",
				"security_codes": 1,
				"printer_host": None,
			}
		)

	def check_in(self, person=None, code=None):
		return frappe.get_doc(
			{
				"doctype": "Function Check-In",
				"function": self.function.name,
				"person": person or self.person.name,
				"security_code": code,
			}
		)

	def test_html_tags_render_one_label_per_check_in_plus_a_pickup_tag(self):
		other = make_person("_Test Tag", "Sibling")
		html = self.settings.render_name_tags([self.check_in(code="K7PX"), self.check_in(other.name, "K7PX")])
		self.assertEqual(html.count('class="name-tag"'), 2)
		self.assertEqual(html.count('class="name-tag pickup"'), 1)
		self.assertIn("Bartholomew-Alexander, _Test Tag", html)
		self.assertIn("_Test Tag Function · May 1, 2031", html)
		self.assertIn("page-width: 4in; page-height: 2in", html)

	def test_long_first_names_shrink_to_fit(self):
		html = self.settings.render_name_tags([self.check_in()])
		self.assertIn('style="font-size: 0.27in"', html)

	def test_no_pickup_tag_without_security_codes(self):
		self.settings.security_codes = 0
		html = self.settings.render_name_tags([self.check_in(code="K7PX")])
		self.assertNotIn('class="name-tag pickup"', html)

	def test_zpl_tags_are_sized_from_the_settings(self):
		self.settings.update({"name_tag_printing": "QZ Tray", "label_dpi": "300"})
		zpl = self.settings.render_name_tags([self.check_in(code="K7PX")])
		self.assertIn("^PW1200", zpl)
		self.assertIn("^LL600", zpl)
		self.assertIn("^FDBartholomew-Alexander^FS", zpl)
		self.assertIn("^FDK7PX^FS", zpl)
		self.assertEqual(zpl.count("^XA"), 2)

	def test_zpl_strips_control_characters_from_names(self):
		person = make_person("Ca^ret", "Til~de")
		self.settings.name_tag_printing = "Zebra Browser Print"
		zpl = self.settings.render_name_tags([self.check_in(person.name)])
		self.assertIn("^FDCaret^FS", zpl)
		self.assertIn("^FDTilde^FS", zpl)

	def test_browser_jobs_return_html_for_the_client(self):
		job = self.settings.print_name_tags([self.check_in()])
		self.assertEqual(job["method"], "Browser")
		self.assertEqual(job["count"], 1)
		self.assertTrue(job["content"].startswith("<!doctype html>"))

	def test_network_printer_sends_zpl_over_a_socket(self):
		self.settings.update(
			{"name_tag_printing": "Network Printer", "printer_host": "10.0.0.5", "printer_port": 9100}
		)
		connection = MagicMock()
		with patch("socket.create_connection", return_value=connection) as create_connection:
			job = self.settings.print_name_tags([self.check_in()])
		create_connection.assert_called_once_with(("10.0.0.5", 9100), timeout=5)
		sent = connection.__enter__.return_value.sendall.call_args[0][0]
		self.assertTrue(sent.startswith(b"^XA"))
		self.assertEqual(job, {"method": "Network Printer", "count": 1, "printed": True})

	def test_unreachable_network_printer_fails_loudly(self):
		self.settings.update({"name_tag_printing": "Network Printer", "printer_host": "10.0.0.5"})
		with patch("socket.create_connection", side_effect=OSError("timed out")):
			with self.assertRaises(ValidationError):
				self.settings.print_name_tags([self.check_in()])

	def test_print_formats_must_match_the_printing_path(self):
		self.settings.zpl_format = "Name Tag"
		with self.assertRaises(ValidationError):
			self.settings.validate()

	def test_print_name_tags_for_persons_needs_no_check_in(self):
		self.settings.save(ignore_permissions=True)
		job = print_name_tags(persons=[self.person.name])
		self.assertIn("Featherstonehaugh", job["content"])
		self.assertNotIn('class="name-tag pickup"', job["content"])

	def test_standard_print_view_renders_the_name_tag(self):
		check_in = self.check_in().insert(ignore_permissions=True)
		html = frappe.get_print("Function Check-In", check_in.name, "Name Tag")
		self.assertIn("Bartholomew-Alexander", html)
		self.assertIn("page-width: 4.0in; page-height: 2.0in", html)
