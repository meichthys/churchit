# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Install-time seeding and versioned patches must be safe to run again."""

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.patches import after_install
from churchit.patches.v1_0 import (
	add_churchit_website_theme,
	add_missionary_map_to_missions_page,
	redesign_home_page,
	rename_agency_logo_field,
	update_default_navbar,
)
from churchit.patches.v1_0 import add_giving_statements_to_portal as portal_patch
from churchit.patches.v1_0 import migrate_contact_fields_to_child_tables as contact_patch
from churchit.patches.v1_0 import set_statement_acknowledgment as acknowledgment_patch
from churchit.tests.helpers import make_address, make_person


class TestAfterInstall(FrappeTestCase):
	def test_execute_is_idempotent(self):
		after_install.execute()
		counts = self._lookup_counts()
		after_install.execute()
		self.assertEqual(self._lookup_counts(), counts)

		self.assertEqual(frappe.db.count("Church"), 1)
		self.assertEqual(frappe.db.count("Bible Book"), 66)
		self.assertTrue(frappe.db.exists("Email Group", "Church Members"))
		self.assertTrue(frappe.db.exists("Module Profile", "Church"))
		self.assertEqual(frappe.get_doc("Website Settings").home_page, "home")
		self.assertEqual(frappe.get_doc("Website Settings").website_theme, "Churchit")

	def _lookup_counts(self):
		return {
			doctype: frappe.db.count(doctype)
			for doctype in (
				"Church",
				"Member Status",
				"Function Type",
				"Function Attendance Type",
				"Position Type",
				"Payment Type",
				"Person Relation Type",
				"Prayer Request Status",
				"Prayer Request Type",
				"Missionary Support Frequency",
				"Group Role",
				"Group Status",
				"Bible Book",
				"Bible Translation",
				"Web Page",
				"Visit Type",
				"Life Event Type",
				"Case Type",
				"Care Request Type",
				"Email Type",
				"Phone Type",
				"Address Type",
			)
		}

	def test_portal_menu_items_are_seeded_once(self):
		after_install._setup_portal_settings()
		after_install._setup_portal_settings()
		menu = frappe.get_doc("Portal Settings").menu
		self.assertEqual([row.route for row in menu].count("memorize"), 1)
		self.assertEqual([row.route for row in menu].count("groups"), 1)
		self.assertEqual(next(row.role for row in menu if row.route == "groups"), "Church User")


class TestVersionedPatches(FrappeTestCase):
	def test_missions_map_is_added_once(self):
		page = frappe.get_doc("Web Page", "missions")
		page.main_section_html = "<p>Existing content</p>"
		page.save(ignore_permissions=True)

		add_missionary_map_to_missions_page.execute()
		add_missionary_map_to_missions_page.execute()

		html = frappe.db.get_value("Web Page", "missions", "main_section_html")
		self.assertEqual(html, add_missionary_map_to_missions_page.MAP_MARKUP + "<p>Existing content</p>")

	def test_agency_logo_rename_is_a_no_op_once_applied(self):
		self.assertFalse(frappe.db.has_column("Missionary Agency", "image_hhbv"))
		rename_agency_logo_field.execute()
		self.assertTrue(frappe.db.has_column("Missionary Agency", "logo"))

	def test_contact_migration_reruns_without_legacy_columns(self):
		self.assertEqual(contact_patch._read_legacy("Person", ["email", "primary_phone"]), [])
		contact_patch.execute()

	def test_person_address_rows_from_legacy_fields(self):
		home, box = "ADDR-HOME", "ADDR-BOX"
		self.assertEqual(
			contact_patch._person_address_rows(
				{"home_address": home, "mailing_address": box, "different_mailing_address": 1}
			),
			[(home, "Home", 0, 1), (box, "Other", 1, 0)],
		)
		self.assertEqual(
			contact_patch._person_address_rows(
				{"home_address": home, "mailing_address": home, "different_mailing_address": 1}
			),
			[(home, "Home", 1, 1)],
		)
		self.assertEqual(contact_patch._person_address_rows({"mailing_address": box}), [(box, "Other", 1, 1)])
		self.assertEqual(contact_patch._person_address_rows({}), [])

	def test_append_only_fills_empty_tables_and_skips_missing_addresses(self):
		person = make_person("_Test Patch", "Person")
		address = make_address("_Test Patch Address").name

		contact_patch._add_addresses(
			"Person", person.name, [("ADDR-GONE", "Home", 1, 1), (address, "Home", 1, 1)]
		)
		contact_patch._add_addresses("Person", person.name, [(address, "Other", 0, 0)])

		rows = frappe.get_all(
			"Postal Address",
			filters={"parent": person.name},
			fields=["address", "address_type", "is_primary"],
		)
		self.assertEqual([(r.address, r.address_type, r.is_primary) for r in rows], [(address, "Home", 1)])

	def test_backfill_sets_notification_address_on_primary_rows_only(self):
		person = make_person("_Test Patch", "Mailer")
		contact_patch._add_email("Person", person.name, "patched@example.com")
		frappe.db.set_value(
			"Email Address", {"parent": person.name}, "notification_address", None, update_modified=False
		)

		contact_patch._backfill_notification_addresses()
		self.assertEqual(
			frappe.db.get_value("Email Address", {"parent": person.name}, "notification_address"),
			"patched@example.com",
		)

	def test_giving_statements_portal_item_is_added_once(self):
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != portal_patch.ROUTE]
		settings.save(ignore_permissions=True)

		portal_patch.execute()
		portal_patch.execute()

		rows = [row for row in frappe.get_doc("Portal Settings").menu if row.route == portal_patch.ROUTE]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].role, "Church User", "members, not staff, reach it from the portal")
		self.assertTrue(rows[0].enabled)

	def test_home_page_redesign_only_replaces_the_shipped_default(self):
		page = frappe.get_doc("Web Page", "home")
		page.main_section_html = redesign_home_page.SHIPPED_DEFAULT
		page.save(ignore_permissions=True)

		redesign_home_page.execute()
		redesign_home_page.execute()

		html = frappe.db.get_value("Web Page", "home", "main_section_html")
		self.assertIn("get_church()", html)
		self.assertNotEqual(html, redesign_home_page.SHIPPED_DEFAULT)

	def test_home_page_redesign_leaves_a_customized_page_alone(self):
		page = frappe.get_doc("Web Page", "home")
		page.main_section_html = "<p>Our custom homepage</p>"
		page.save(ignore_permissions=True)

		redesign_home_page.execute()

		self.assertEqual(
			frappe.db.get_value("Web Page", "home", "main_section_html"), "<p>Our custom homepage</p>"
		)

	def test_navbar_gains_calendar_after_ministries_and_loses_locations(self):
		settings = frappe.get_doc("Website Settings")
		settings.top_bar_items = []
		for item in [
			{"label": "Ministries", "url": "/ministries", "right": 1},
			{"label": "Locations", "url": "/locations", "right": 1},
			{"label": "Give", "url": "/give", "right": 1},
		]:
			settings.append("top_bar_items", item)
		settings.save(ignore_permissions=True)

		update_default_navbar.execute()
		update_default_navbar.execute()

		rows = frappe.get_doc("Website Settings").top_bar_items
		self.assertEqual([row.label for row in rows], ["Ministries", "Calendar", "Give"])
		self.assertEqual([row.idx for row in rows], [1, 2, 3])

	def test_navbar_leaves_a_repointed_locations_entry_alone(self):
		settings = frappe.get_doc("Website Settings")
		settings.top_bar_items = []
		settings.append("top_bar_items", {"label": "Locations", "url": "/our-campuses", "right": 1})
		settings.save(ignore_permissions=True)

		update_default_navbar.execute()

		labels = [row.label for row in frappe.get_doc("Website Settings").top_bar_items]
		self.assertIn("Locations", labels, "a church that re-pointed the link keeps it")
		self.assertIn("Calendar", labels)

	def _reset_website_theme(self):
		frappe.db.set_single_value("Website Settings", "website_theme", "Standard")
		frappe.delete_doc("Website Theme", "Churchit", force=True)

	def test_website_theme_moves_a_site_on_standard_to_churchit(self):
		self._reset_website_theme()

		add_churchit_website_theme.execute()
		add_churchit_website_theme.execute()

		self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Churchit")
		self.assertEqual(frappe.db.count("Website Theme", {"theme": "Churchit"}), 1)

	def test_website_theme_compiles_this_app_into_the_stylesheet(self):
		self._reset_website_theme()

		add_churchit_website_theme.execute()

		theme = frappe.get_doc("Website Theme", "Churchit")
		self.assertTrue(theme.custom, "user-owned, so a church can edit it")
		self.assertIn('@import "churchit/public/scss/website"', theme.theme_scss)
		stylesheet = frappe.utils.get_site_path("public", theme.theme_url.removeprefix("/"))
		self.assertIn("--ch-grad", open(stylesheet).read())

	def test_website_theme_leaves_a_church_that_picked_its_own_alone(self):
		own_theme = frappe.get_doc({"doctype": "Website Theme", "theme": "_Test Church Theme"})
		own_theme.insert(ignore_permissions=True)
		frappe.db.set_single_value("Website Settings", "website_theme", own_theme.name)

		add_churchit_website_theme.execute()

		self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), own_theme.name)
		self.assertTrue(frappe.db.exists("Website Theme", "Churchit"), "the theme is still offered")

	def test_statement_acknowledgment_only_fills_a_blank_value(self):
		frappe.db.set_single_value("Giving Settings", "statement_acknowledgment", "")
		acknowledgment_patch.execute()
		seeded = frappe.db.get_single_value("Giving Settings", "statement_acknowledgment")
		self.assertEqual(seeded, acknowledgment_patch.DEFAULT_TEXT)

		frappe.db.set_single_value("Giving Settings", "statement_acknowledgment", "_Test custom wording.")
		acknowledgment_patch.execute()
		self.assertEqual(
			frappe.db.get_single_value("Giving Settings", "statement_acknowledgment"),
			"_Test custom wording.",
			"a church that worded its own keeps it",
		)
