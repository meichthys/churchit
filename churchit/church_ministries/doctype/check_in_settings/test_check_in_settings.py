# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import MagicMock, patch

import frappe
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_ministries.doctype.check_in_settings.check_in_settings import (
	VOLUNTEER_NAME_TAG,
	add_volunteer_tag_format,
)
from churchit.church_ministries.doctype.function_check_in.function_check_in import print_name_tags
from churchit.tests.helpers import RollbackEachTest, make_function, make_person


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
				"print_allergies": 0,
				"printer_host": None,
			}
		)
		self.settings.set("tag_formats", [])

	def check_in(self, person=None, code=None, kind=None):
		return frappe.get_doc(
			{
				"doctype": "Function Check-In",
				"function": self.function.name,
				"person": person or self.person.name,
				"security_code": code,
				"check_in_kind": kind,
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

	def test_allergies_print_only_when_the_settings_ask_for_them(self):
		allergic = make_person("_Test Tag", "Allergic", alergies="Peanuts")
		for method in ("Browser", "QZ Tray"):
			self.settings.update({"name_tag_printing": method, "print_allergies": 0})
			self.assertNotIn(
				"Peanuts", self.settings.render_name_tags([self.check_in(allergic.name)]), method
			)

			self.settings.print_allergies = 1
			self.assertIn(
				"Allergies: Peanuts", self.settings.render_name_tags([self.check_in(allergic.name)]), method
			)
			self.assertNotIn("Allergies", self.settings.render_name_tags([self.check_in()]), method)

	def test_tags_print_the_nickname_in_place_of_the_first_name(self):
		peggy = make_person("Margaret", "_Test Tag", nickname="Peggy")
		check_ins = [self.check_in(peggy.name, "K7PX"), self.check_in(code="K7PX")]
		for method in ("Browser", "QZ Tray"):
			self.settings.name_tag_printing = method
			tags = self.settings.render_name_tags(check_ins)
			self.assertIn("Peggy", tags, method)
			self.assertNotIn("Margaret", tags, method)
		self.assertIn("Peggy, Bartholomew-Alexander", tags)

	def test_html_tags_escape_what_members_type(self):
		person = make_person("<b>Bold</b>", alergies="<script>x</script>")
		self.settings.print_allergies = 1
		html = self.settings.render_name_tags([self.check_in(person.name)])
		self.assertIn("&lt;b&gt;Bold&lt;/b&gt;", html)
		self.assertNotIn("<script>", html)

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

	def add_volunteer_row(self):
		self.settings.append(
			"tag_formats", {"check_in_kind": "Volunteer", "name_tag_format": VOLUNTEER_NAME_TAG}
		)

	def test_a_check_in_renders_the_format_of_its_kind(self):
		self.add_volunteer_row()
		html = self.settings.render_name_tags([self.check_in(kind="Volunteer")])
		self.assertIn('class="name-tag volunteer"', html)

	def test_a_kind_with_no_row_renders_the_default_format(self):
		self.add_volunteer_row()
		html = self.settings.render_name_tags([self.check_in(kind="Guest"), self.check_in(kind="Regular")])
		self.assertEqual(html.count('class="name-tag"'), 2)
		self.assertNotIn("volunteer", html)

	def test_a_kind_row_without_a_zpl_format_prints_the_default_zpl(self):
		self.settings.update({"name_tag_printing": "QZ Tray"})
		self.add_volunteer_row()
		zpl = self.settings.render_name_tags([self.check_in(kind="Volunteer")])
		self.assertTrue(zpl.startswith("^XA"))

	def test_pickup_tags_carry_a_qr_code_of_the_security_code(self):
		html = self.settings.render_name_tags([self.check_in(code="K7PX")])
		pickup = html[html.index('class="name-tag pickup"') :]
		self.assertIn('<img class="qr-code" src="data:image/svg+xml;base64,', pickup)

		self.settings.name_tag_printing = "QZ Tray"
		zpl = self.settings.render_name_tags([self.check_in(code="K7PX")])
		self.assertEqual(zpl.count("^BQN"), 1)
		self.assertIn("^FDQA,K7PX^FS", zpl)

	def test_a_tag_format_row_must_match_its_printing_path(self):
		for field, wrong in (("name_tag_format", "Zebra Name Tag"), ("zpl_format", "Name Tag")):
			self.settings.set("tag_formats", [{"check_in_kind": "Guest", field: wrong}])
			with self.assertRaises(ValidationError, msg=field):
				self.settings.validate()

	def test_one_tag_format_row_for_each_kind(self):
		self.settings.set(
			"tag_formats",
			[{"check_in_kind": "Guest", "name_tag_format": "Name Tag"}] * 2,
		)
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


class TestPrinterPerChurch(FrappeTestCase):
	"""Each campus has its own label printer, so one host cannot serve them all."""

	def setUp(self):
		self.settings = frappe.get_single("Check-In Settings")
		self.settings.update(
			{
				"name_tag_printing": "Network Printer",
				"printer_host": "10.0.0.5",
				"printer_port": 9100,
				"printer_name": "Main Desk",
				"label_width": 4,
				"label_height": 2,
			}
		)
		self.settings.set("printers", [])

	def test_a_church_without_a_row_keeps_the_site_wide_printer(self):
		resolved = self.settings.for_church("CHR-BRANCH")
		self.assertEqual(resolved.printer_host, "10.0.0.5")
		self.assertIs(resolved, self.settings, "no row means no copy is needed")

	def test_a_church_with_a_row_prints_to_its_own_printer(self):
		self.settings.append(
			"printers",
			{"church": "CHR-BRANCH", "printer_host": "10.9.9.9", "printer_name": "Hall Printer"},
		)

		resolved = self.settings.for_church("CHR-BRANCH")
		self.assertEqual(resolved.printer_host, "10.9.9.9")
		self.assertEqual(resolved.printer_name, "Hall Printer")
		# Fields the row leaves blank still come from the settings above it.
		self.assertEqual(resolved.printer_port, 9100)
		self.assertEqual(resolved.name_tag_printing, "Network Printer")
		self.assertEqual(resolved.label_width, 4)

	def test_resolving_leaves_the_stored_settings_alone(self):
		self.settings.append("printers", {"church": "CHR-BRANCH", "printer_host": "10.9.9.9"})

		self.settings.for_church("CHR-BRANCH")

		self.assertEqual(self.settings.printer_host, "10.0.0.5")

	def test_another_church_is_unaffected(self):
		self.settings.append("printers", {"church": "CHR-BRANCH", "printer_host": "10.9.9.9"})
		self.assertEqual(self.settings.for_church("CHR-OTHER").printer_host, "10.0.0.5")


class TestVolunteerTagFormat(RollbackEachTest):
	def tag_formats(self):
		return [
			(row.check_in_kind, row.name_tag_format)
			for row in frappe.get_single("Check-In Settings").tag_formats
		]

	def test_the_seed_adds_one_volunteer_row(self):
		settings = frappe.get_single("Check-In Settings")
		settings.set("tag_formats", [])
		settings.save(ignore_permissions=True)

		add_volunteer_tag_format()
		add_volunteer_tag_format()

		self.assertEqual(self.tag_formats(), [("Volunteer", VOLUNTEER_NAME_TAG)])

	def test_the_seed_keeps_a_churchs_own_volunteer_row(self):
		settings = frappe.get_single("Check-In Settings")
		settings.set("tag_formats", [{"check_in_kind": "Volunteer", "name_tag_format": "Name Tag"}])
		settings.save(ignore_permissions=True)

		add_volunteer_tag_format()

		self.assertEqual(self.tag_formats(), [("Volunteer", "Name Tag")])
