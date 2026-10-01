# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBulletinSectionsPerChurch(FrappeTestCase):
	"""A row replaces the whole set, because an unticked box cannot mean "inherit"."""

	def setUp(self):
		self.settings = frappe.get_single("Bulletin Settings")
		self.settings.update({"show_birthdays": 1, "show_missionary": 1, "celebration_days": 7})
		self.settings.set("church_sections", [])

	def test_a_church_without_a_row_uses_the_site_wide_sections(self):
		resolved = self.settings.for_church("CHR-BRANCH")
		self.assertIs(resolved, self.settings)
		self.assertTrue(resolved.show_birthdays)

	def test_a_church_with_a_row_uses_only_that_row(self):
		self.settings.append(
			"church_sections",
			{"church": "CHR-BRANCH", "show_birthdays": 0, "show_missionary": 1, "celebration_days": 3},
		)

		resolved = self.settings.for_church("CHR-BRANCH")
		self.assertFalse(resolved.show_birthdays, "the row's unticked box wins, it does not inherit")
		self.assertTrue(resolved.show_missionary)
		self.assertEqual(resolved.celebration_days, 3)

	def test_resolving_leaves_the_stored_settings_alone(self):
		self.settings.append("church_sections", {"church": "CHR-BRANCH", "show_birthdays": 0})

		self.settings.for_church("CHR-BRANCH")

		self.assertTrue(self.settings.show_birthdays)

	def test_another_church_is_unaffected(self):
		self.settings.append("church_sections", {"church": "CHR-BRANCH", "show_birthdays": 0})
		self.assertTrue(self.settings.for_church("CHR-OTHER").show_birthdays)
