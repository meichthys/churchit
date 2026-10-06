# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Install-time seeding and versioned patches must be safe to run again."""

import os
import tempfile
from unittest import mock

import frappe
from frappe.model.naming import NamingSeries
from frappe.modules.patch_handler import update_patch_log
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.website_theme.website_theme import WebsiteTheme

from churchit.church_scope import is_multi_church
from churchit.patches import after_install
from churchit.patches.v1_0 import (
	add_attendance_to_portal,
	add_churchit_website_theme,
	add_default_address_template,
	add_missionary_map_to_missions_page,
	add_unsynced_default_records,
	redesign_home_page,
	remove_knowledge_base,
	rename_agency_logo_field,
	scope_website_pages_to_church,
	seed_naming_series_counters,
	setup_bulletins,
	update_default_navbar,
)
from churchit.patches.v1_0 import add_giving_statements_to_portal as portal_patch
from churchit.patches.v1_0 import migrate_contact_fields_to_child_tables as contact_patch
from churchit.patches.v1_0 import number_repeated_bible_translation_abbreviations as abbreviation_patch
from churchit.patches.v1_0 import replace_bible_records_with_references as bible_patch
from churchit.patches.v1_0 import set_statement_acknowledgment as acknowledgment_patch
from churchit.tests.helpers import RollbackEachTest, make_address, make_function, make_person


class TestUnsyncedDefaultRecords(FrappeTestCase):
	"""Letter Head and Email Template ship as JSON that Frappe's sync never imports."""

	TEMPLATES = ("Donation Acknowledgment", "Birthday Greeting", "New Member Welcome", "Visitor Follow-Up")

	def test_the_patch_seeds_the_letterhead_and_the_email_templates(self):
		frappe.db.delete("Letter Head", {"name": "Church Letter Head"})
		frappe.db.delete("Email Template", {"name": ("in", self.TEMPLATES)})

		add_unsynced_default_records.execute()

		self.assertTrue(frappe.db.exists("Letter Head", "Church Letter Head"))
		for template in self.TEMPLATES:
			self.assertTrue(frappe.db.exists("Email Template", template), template)

	def test_running_it_again_leaves_a_church_s_edits_alone(self):
		add_unsynced_default_records.execute()
		frappe.db.set_value("Letter Head", "Church Letter Head", "content", "<p>Ours</p>")

		add_unsynced_default_records.execute()

		self.assertEqual(frappe.db.get_value("Letter Head", "Church Letter Head", "content"), "<p>Ours</p>")

	def test_it_never_demotes_a_letterhead_the_church_already_made_default(self):
		frappe.db.delete("Letter Head", {"name": "Church Letter Head"})
		theirs = frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": "_Test Church Own Letterhead",
				"source": "HTML",
				"content": "<p>Theirs</p>",
				"is_default": 1,
			}
		).insert(ignore_permissions=True)

		add_unsynced_default_records.execute()

		self.assertTrue(frappe.db.get_value("Letter Head", theirs.name, "is_default"))
		self.assertFalse(frappe.db.get_value("Letter Head", "Church Letter Head", "is_default"))


class TestAfterInstall(FrappeTestCase):
	def test_execute_is_idempotent(self):
		after_install.execute()
		counts = self._lookup_counts()
		after_install.execute()
		self.assertEqual(self._lookup_counts(), counts)

		self.assertEqual(frappe.db.count("Church", {"parent_church": ("is", "not set")}), 1)
		self.assertTrue(frappe.db.exists("Bible Translation", {"source": "Free Use Bible API"}))
		self.assertTrue(frappe.db.exists("Email Group", "Church Members"))
		self.assertTrue(frappe.db.exists("Module Profile", "Church"))
		self.assertEqual(frappe.get_doc("Website Settings").home_page, "home")
		self.assertEqual(frappe.get_doc("Website Settings").website_theme, "Churchit")
		self.assertTrue(frappe.db.exists("Address Template", {"is_default": 1}))
		self.assertTrue(frappe.db.exists("Letter Head", "Church Letter Head"))

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
				"Bible Translation",
				"Web Page",
				"Visit Type",
				"Life Event Type",
				"Case Type",
				"Care Request Type",
				"Email Type",
				"Phone Type",
				"Address Type",
				"Address Template",
			)
		}

	def test_portal_menu_items_are_seeded_once(self):
		after_install._setup_portal_settings()
		after_install._setup_portal_settings()
		menu = frappe.get_doc("Portal Settings").menu
		self.assertEqual([row.route for row in menu].count("memorize"), 1)
		self.assertEqual([row.route for row in menu].count("groups"), 1)
		self.assertEqual(next(row.role for row in menu if row.route == "groups"), "Church User")

	def test_only_the_default_translation_downloads_up_front(self):
		"""The BSB downloads at install; every other free translation waits to be opened."""
		self.assertFalse(after_install.should_skip_download("BSB", "BSB"))
		self.assertTrue(after_install.should_skip_download("KJV", "eng_kjv"))
		self.assertFalse(after_install.should_skip_download("NIV", None))


class TestVersionedPatches(FrappeTestCase):
	def test_naming_counters_seed_from_highest_existing_name(self):
		series = NamingSeries("PRSN-.####")
		highest = max(int(n[5:]) for n in frappe.get_all("Person", pluck="name") if n[5:].isdigit())
		series.update_counter(0)

		seed_naming_series_counters.execute()
		self.assertEqual(series.get_current_value(), highest)

		series.update_counter(highest + 5)
		seed_naming_series_counters.execute()
		self.assertEqual(series.get_current_value(), highest + 5)

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

	def test_portal_menu_items_are_added_once(self):
		for patch in (portal_patch, add_attendance_to_portal):
			with self.subTest(patch.ROUTE):
				settings = frappe.get_doc("Portal Settings")
				settings.menu = [row for row in settings.menu if row.route != patch.ROUTE]
				settings.save(ignore_permissions=True)

				patch.execute()
				patch.execute()

				rows = [row for row in frappe.get_doc("Portal Settings").menu if row.route == patch.ROUTE]
				self.assertEqual(len(rows), 1)
				self.assertEqual(rows[0].role, "Church User", "members, not staff, reach it from the portal")
				self.assertTrue(rows[0].enabled)

	def test_knowledge_base_is_taken_out_of_the_app(self):
		settings = frappe.get_doc("Portal Settings")
		settings.append(
			"custom_menu",
			{
				"title": "Help Articles",
				"route": "Help Article",
				"reference_doctype": "Help Article",
				"enabled": 1,
			},
		)
		settings.save(ignore_permissions=True)
		if not frappe.db.exists("Number Card", "Help Articles"):
			frappe.get_doc(
				{
					"doctype": "Number Card",
					"label": "Help Articles",
					"type": "Document Type",
					"document_type": "Help Article",
					"function": "Count",
				}
			).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": "Help Article",
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": "Church User",
				"read": 1,
			}
		).insert(ignore_permissions=True)

		remove_knowledge_base.execute()
		remove_knowledge_base.execute()

		settings = frappe.get_doc("Portal Settings")
		menu = [row.reference_doctype for row in settings.menu + settings.custom_menu]
		self.assertNotIn("Help Article", menu)
		self.assertIn("Function Sign-Up", menu, "the rest of the menu stays")
		self.assertFalse(frappe.db.exists("Number Card", "Help Articles"))
		self.assertFalse(
			frappe.db.exists("Custom DocPerm", {"parent": "Help Article", "role": "Church User"})
		)

	def test_bulletins_setup_seeds_once_and_retires_the_old_print_format(self):
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != setup_bulletins.ROUTE]
		settings.save(ignore_permissions=True)
		bulletin_settings = frappe.get_doc("Bulletin Settings")
		bulletin_settings.set("roles", [])
		bulletin_settings.save(ignore_permissions=True)
		if not frappe.db.exists("Print Format", "Sunday Bulletin"):
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": "Sunday Bulletin",
					"doc_type": "Function",
					"standard": "No",
				}
			).insert(ignore_permissions=True)

		setup_bulletins.execute()
		setup_bulletins.execute()

		self.assertFalse(frappe.db.exists("Print Format", "Sunday Bulletin"))
		rows = [row for row in frappe.get_doc("Portal Settings").menu if row.route == setup_bulletins.ROUTE]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0].role, "Church User")
		roles = [row.position_type for row in frappe.get_doc("Bulletin Settings").roles]
		self.assertEqual(roles, ["Pastor", "Elder", "Deacon"])

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

	def test_website_pages_gain_church_scoping_and_keep_their_edits(self):
		page = frappe.get_doc("Web Page", "home")
		page.main_section_html = (
			"<p>Our own hero</p>\n"
			'{%- set sermons = frappe.get_all("Sermon", filters={"publish": 1}) -%}\n'
			'{{ frappe.db.count("Ministry", {"publish": 1}) }}'
		)
		page.save(ignore_permissions=True)

		scope_website_pages_to_church.execute()
		scope_website_pages_to_church.execute()

		html = frappe.db.get_value("Web Page", "home", "main_section_html")
		self.assertIn("<p>Our own hero</p>", html)
		self.assertIn("filters=selected_church_filters(publish=1)", html)
		self.assertIn('frappe.db.count("Ministry", selected_church_filters(publish=1))', html)
		self.assertNotIn('{"publish": 1}', html)

	def test_website_pages_keep_a_query_the_church_rewrote(self):
		page = frappe.get_doc("Web Page", "sermons")
		page.main_section_html = '{%- set all = frappe.get_all("Sermon", filters={"publish": 0}) -%}'
		page.save(ignore_permissions=True)

		scope_website_pages_to_church.execute()

		self.assertEqual(
			frappe.db.get_value("Web Page", "sermons", "main_section_html"),
			'{%- set all = frappe.get_all("Sermon", filters={"publish": 0}) -%}',
		)

	def _locations_page(self, html):
		"""The retired Locations Web Page as a site installed before it moved still has it."""
		name = frappe.db.get_value("Web Page", {"route": "locations"})
		page = (
			frappe.get_doc("Web Page", name)
			if name
			else frappe.new_doc("Web Page").update({"title": "Locations", "route": "locations"})
		)
		page.update({"published": 1, "content_type": "HTML", "main_section_html": html})
		return page.save(ignore_permissions=True)

	def test_the_retired_locations_page_stops_shadowing_the_app_page(self):
		page = self._locations_page(scope_website_pages_to_church.SHIPPED_LOCATIONS)

		scope_website_pages_to_church.execute()

		self.assertEqual(frappe.db.get_value("Web Page", page.name, "published"), 0)

	def test_a_church_s_own_locations_page_stays_published(self):
		page = self._locations_page("<p>Two campuses, one church.</p>")

		scope_website_pages_to_church.execute()

		self.assertEqual(frappe.db.get_value("Web Page", page.name, "published"), 1)

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

	def _compile_themes_into_temporary_folder(self):
		"""Compiled stylesheets are files, which the test transaction cannot roll
		back; frappe keeps only the two newest per theme, so compiling into the
		site's files folder would delete the stylesheet the live theme points at."""
		folder = self.enterContext(tempfile.TemporaryDirectory())
		self.enterContext(mock.patch("frappe.utils.get_files_path", return_value=folder))
		return folder

	def _skip_theme_compile(self):
		"""Compiling a theme runs sass for about a second; only the stylesheet test needs it."""
		self.enterContext(mock.patch.object(WebsiteTheme, "generate_bootstrap_theme"))

	def _reset_website_theme(self):
		folder = self._compile_themes_into_temporary_folder()
		frappe.db.set_single_value("Website Settings", "website_theme", "Standard")
		frappe.delete_doc("Website Theme", "Churchit", force=True)
		return folder

	def test_website_theme_moves_a_site_on_standard_to_churchit(self):
		self._skip_theme_compile()
		self._reset_website_theme()

		add_churchit_website_theme.execute()
		add_churchit_website_theme.execute()

		self.assertEqual(frappe.db.get_single_value("Website Settings", "website_theme"), "Churchit")
		self.assertEqual(frappe.db.count("Website Theme", {"theme": "Churchit"}), 1)

	def test_website_theme_compiles_this_app_into_the_stylesheet(self):
		folder = self._reset_website_theme()

		add_churchit_website_theme.execute()

		theme = frappe.get_doc("Website Theme", "Churchit")
		self.assertTrue(theme.custom, "user-owned, so a church can edit it")
		self.assertIn('@import "churchit/public/scss/website"', theme.theme_scss)
		self.assertTrue(theme.theme_url.startswith("/files/website_theme/"))
		stylesheet = os.path.join(folder, os.path.basename(theme.theme_url))
		self.assertIn("--ch-grad", open(stylesheet).read())

	def test_website_theme_leaves_a_church_that_picked_its_own_alone(self):
		self._skip_theme_compile()
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

	def test_default_address_template_is_added_when_none_exists(self):
		frappe.db.delete("Address Template")
		add_default_address_template.execute()
		add_default_address_template.execute()
		self.assertEqual(frappe.db.count("Address Template"), 1)
		self.assertTrue(frappe.db.exists("Address Template", {"is_default": 1}))

		display = make_address("_Test Template Church", state="IL", pincode="62701").get_display()
		self.assertIn("Springfield, IL 62701", display)

	def test_default_address_template_leaves_a_church_that_made_its_own_alone(self):
		frappe.db.delete("Address Template")
		own = frappe.get_doc(
			{"doctype": "Address Template", "country": "Canada", "is_default": 1, "template": "{{ city }}"}
		).insert(ignore_permissions=True)
		add_default_address_template.execute()
		self.assertEqual(frappe.db.count("Address Template"), 1)
		self.assertEqual(frappe.db.get_value("Address Template", own.name, "template"), "{{ city }}")

	def test_default_address_template_promotes_an_existing_one_for_the_country(self):
		frappe.db.delete("Address Template")
		country = frappe.db.get_single_value("System Settings", "country") or "United States"
		frappe.get_doc({"doctype": "Address Template", "country": country, "template": "{{ city }}"}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value("Address Template", country, "is_default", 0)
		add_default_address_template.execute()
		self.assertEqual(frappe.db.count("Address Template"), 1)
		self.assertEqual(frappe.db.get_value("Address Template", country, "is_default"), 1)


class TestBibleReferencePatch(FrappeTestCase):
	"""Bible Book, Verse and Reference records give way to references written as text."""

	def test_repeated_abbreviations_are_numbered_oldest_first(self):
		rows = [("King James Version", "KJV"), ("KJV Cambridge", "kjv"), ("Other", "KJV"), ("Blank", None)]
		self.assertEqual(
			abbreviation_patch.get_renumbered(rows),
			[("KJV Cambridge", "kjv 2"), ("Other", "KJV 3"), ("Blank", "Blank")],
		)

	def test_a_reference_is_written_out_from_its_verses(self):
		psalm = frappe._dict(
			book="Psalms", chapter="23", verse="1", end_book="Psalms", end_chapter="23", end_verse="6"
		)
		self.assertEqual(bible_patch.tidy(bible_patch.passage_text(psalm)), "Psalms 23:1-6")
		john = frappe._dict(book="John", chapter="3", verse="16", end_book=None)
		self.assertEqual(bible_patch.passage_text(john), "John 3:16")

	def test_a_link_becomes_its_reference_text(self):
		references = {"Psalms 23:1 - Psalms 23:6 (KJV)": ("Psalms 23:1-6", "KJV")}
		self.assertEqual(
			bible_patch.resolve(references, "Psalms 23:1 - Psalms 23:6 (KJV)"), ("Psalms 23:1-6", "KJV")
		)
		# A link to a record that no longer exists is read from its name.
		self.assertEqual(bible_patch.resolve(references, "John 3:16 (KJV)"), ("John 3:16", None))
		# Text pythonbible cannot read is kept as written.
		self.assertEqual(bible_patch.resolve(references, "Hezekiah 1:1"), ("Hezekiah 1:1", None))

	def test_a_slide_showing_a_retired_record_becomes_a_scripture_slide(self):
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": "_Test Patched Sermon", "slides": [{"scripture": "John 3:16"}]}
		).insert(ignore_permissions=True)
		row = sermon.slides[0].name
		frappe.db.set_value(
			"Sermon Slide",
			row,
			{"scripture": None, "slide_type": "Bible Reference", "slide": "Romans 8:28 (ESV)"},
		)
		bible_patch.convert_slides({"Romans 8:28 (ESV)": ("Romans 8:28", "ESV")})
		self.assertEqual(
			frappe.db.get_value("Sermon Slide", row, ["slide_type", "slide", "scripture", "translation"]),
			(None, None, "Romans 8:28", "ESV"),
		)

	def test_an_order_of_worship_item_keeps_the_passage_in_its_description(self):
		function = make_function("_Test Patched Service", schedule=[{"description": "Scripture reading"}])
		row = function.schedule[0].name
		frappe.db.set_value(
			"Function Schedule", row, {"item_type": "Bible Reference", "item": "Psalms 23:1 (KJV)"}
		)
		bible_patch.convert_schedules({})
		self.assertEqual(
			frappe.db.get_value("Function Schedule", row, ["item_type", "item", "description"]),
			(None, None, "Scripture reading\nPsalms 23:1"),
		)

	def test_a_link_that_cannot_be_empty_is_removed_and_noted_on_its_parent(self):
		person = make_person("_Test Patch", "Prayer").name
		prayer = frappe.get_doc(
			{
				"doctype": "Prayer",
				"person": person,
				"date": frappe.utils.now_datetime(),
				"topics": [{"topic_type": "Person", "topic": person, "prayer": "For strength"}],
			}
		).insert(ignore_permissions=True)
		row = prayer.topics[0].name
		frappe.db.set_value("Prayer Topic", row, {"topic_type": "Bible Verse", "topic": "John 3:16"})

		bible_patch.remove_required_links({})

		self.assertFalse(frappe.db.exists("Prayer Topic", row))
		note = frappe.db.get_value(
			"Comment", {"reference_doctype": "Prayer", "reference_name": prayer.name}, "content"
		)
		self.assertIn("John 3:16", note)
		self.assertIn("For strength", note)

	def test_the_shipped_beliefs_page_shows_the_new_field(self):
		page = frappe.get_doc("Web Page", "beliefs")
		page.main_section_html = f"<div>\n{bible_patch.SHIPPED_BELIEF_REFERENCES}\n</div>"
		page.save(ignore_permissions=True)

		bible_patch.rewrite_beliefs_page()

		html = frappe.db.get_value("Web Page", "beliefs", "main_section_html")
		self.assertIn(bible_patch.BELIEF_REFERENCES, html)
		self.assertNotIn("Bible Reference", html)

	def test_running_again_changes_nothing_and_downloads_nothing(self):
		fields = ["name", "bible_reference", "translation"]
		before = frappe.get_all("Bible Memory Item", fields=fields, order_by="name")
		with mock.patch("frappe.enqueue_doc") as enqueue:
			bible_patch.execute()
		self.assertEqual(frappe.get_all("Bible Memory Item", fields=fields, order_by="name"), before)
		enqueue.assert_not_called()


class TestPreModelSync(RollbackEachTest):
	"""Pre-model-sync patches run on the schema of the version being upgraded."""

	PATCH = "churchit.patches.v1_0._test_pre_model_sync"

	def tearDown(self):
		super().tearDown()
		frappe.clear_cache(doctype="Church Features")

	def record_a_patch(self):
		frappe.clear_cache(doctype="Church Features")
		frappe.db.value_cache.pop("Church Features", None)
		update_patch_log(self.PATCH)
		self.assertTrue(frappe.db.exists("Patch Log", {"patch": self.PATCH}))

	def test_a_patch_is_recorded_before_the_multi_church_switch_is_synced(self):
		frappe.db.delete("DocField", {"parent": "Church Features", "fieldname": "enable_multi_church"})
		self.record_a_patch()
		self.assertFalse(is_multi_church())

	def test_a_patch_is_recorded_before_church_features_is_synced(self):
		frappe.db.delete("DocType", "Church Features")
		self.record_a_patch()
		self.assertFalse(is_multi_church())
