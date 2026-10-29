# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Install-time seeding and versioned patches must be safe to run again."""

import os
import tempfile
from unittest import mock

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
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
	add_marital_statuses,
	add_ministry_teams,
	add_missionary_map_to_missions_page,
	add_missionary_statuses,
	add_personal_details_and_care_requests_to_portal,
	add_pledges_to_portal,
	add_unsynced_default_records,
	clear_unknown_person_sources,
	list_missionary_people_in_a_table,
	mark_check_in_walk_ins_as_visitors,
	move_copied_function_schedules,
	move_email_template_bodies_to_html,
	move_to_the_apps_screen_and_dock,
	redesign_home_page,
	remove_avery_label_format,
	remove_duplicate_new_members_chart,
	remove_email_group_onboarding,
	remove_knowledge_base,
	remove_permlevel_fields_from_person_versions,
	remove_private_fields_from_versions,
	rename_agency_logo_field,
	restamp_shared_fund_transfers,
	restore_shipped_people_charts,
	scope_website_pages_to_church,
	seed_naming_series_counters,
	set_church_website,
	set_display_names,
	setup_bulletins,
	split_membership_from_member_status,
	update_default_navbar,
)
from churchit.patches.v1_0 import add_giving_statements_to_portal as portal_patch
from churchit.patches.v1_0 import migrate_contact_fields_to_child_tables as contact_patch
from churchit.patches.v1_0 import number_repeated_bible_translation_abbreviations as abbreviation_patch
from churchit.patches.v1_0 import replace_bible_records_with_references as bible_patch
from churchit.patches.v1_0 import replace_head_of_household_with_primary_contact as primary_contact_patch
from churchit.patches.v1_0 import set_statement_acknowledgment as acknowledgment_patch
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	ensure_user,
	make_address,
	make_function,
	make_person,
)


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
				"Marital Status",
				"Membership Type",
				"Function Type",
				"Function Attendance Type",
				"Position Type",
				"Payment Type",
				"Person Relation Type",
				"Prayer Request Status",
				"Prayer Request Type",
				"Missionary Status",
				"Missionary Support Frequency",
				"Group Role",
				"Group Status",
				"Group Type",
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

	def test_missionary_person_moves_into_the_people_table_once(self):
		if not frappe.db.has_column("Missionary", "person"):
			self.skipTest("this site never had the Missionary person column")
		person = make_person("_Test", "Patch Missionary").name
		missionary = frappe.get_doc({"doctype": "Missionary", "title": "_Test Patch Missionary"}).insert(
			ignore_permissions=True
		)
		frappe.db.set_value("Missionary", missionary.name, "person", person, update_modified=False)

		list_missionary_people_in_a_table.execute()
		list_missionary_people_in_a_table.execute()

		missionary.reload()
		self.assertEqual([row.person for row in missionary.people], [person])

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
		for patch in (portal_patch, add_attendance_to_portal, add_pledges_to_portal):
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

	def test_personal_details_and_care_requests_are_added_to_the_portal_once(self):
		routes = [item["route"] for item in add_personal_details_and_care_requests_to_portal.ITEMS]
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route not in routes]
		settings.save(ignore_permissions=True)

		add_personal_details_and_care_requests_to_portal.execute()
		add_personal_details_and_care_requests_to_portal.execute()

		menu = frappe.get_doc("Portal Settings").menu
		for route in routes:
			rows = [row for row in menu if row.route == route]
			self.assertEqual(len(rows), 1, route)
			self.assertEqual(rows[0].role, "Church User", "members, not staff, reach it from the portal")

	def test_the_install_time_people_charts_give_way_to_the_shipped_ones(self):
		"""Install's own Members chart counted Life Event rows, which carry no church."""
		frappe.db.set_value(
			"Dashboard Chart", "Members", {"is_standard": 0, "chart_type": "Count", "source": None}
		)

		restore_shipped_people_charts.execute()

		chart = frappe.get_doc("Dashboard Chart", "Members")
		self.assertEqual((chart.is_standard, chart.chart_type, chart.source), (1, "Custom", "Life Events"))

	def test_the_duplicate_new_members_chart_goes_unless_a_dashboard_uses_it(self):
		def make_chart():
			return frappe.get_doc(
				{
					"doctype": "Dashboard Chart",
					"chart_name": remove_duplicate_new_members_chart.CHART,
					"chart_type": "Count",
					"document_type": "Person",
					"based_on": "creation",
					"filters_json": "[]",
					"timeseries": 1,
					"time_interval": "Monthly",
					"timespan": "Last Year",
				}
			).insert(ignore_permissions=True)

		make_chart()
		remove_duplicate_new_members_chart.execute()
		self.assertFalse(frappe.db.exists("Dashboard Chart", remove_duplicate_new_members_chart.CHART))

		frappe.get_doc(
			{
				"doctype": "Dashboard",
				"dashboard_name": "_Test New Members Dashboard",
				"charts": [{"chart": make_chart().name}],
			}
		).insert(ignore_permissions=True)
		remove_duplicate_new_members_chart.execute()
		self.assertTrue(frappe.db.exists("Dashboard Chart", remove_duplicate_new_members_chart.CHART))

	def test_the_email_group_onboarding_is_taken_out(self):
		frappe.get_doc(
			{
				"doctype": "Onboarding Step",
				"__newname": remove_email_group_onboarding.NAME,
				"title": remove_email_group_onboarding.NAME,
				"action": "Go to Page",
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)
		frappe.get_doc(
			{
				"doctype": "Form Tour",
				"name": remove_email_group_onboarding.NAME,
				"title": remove_email_group_onboarding.NAME,
				"reference_doctype": "Email Group",
				"steps": [{"fieldname": "title", "title": "Group Name", "description": "_Test"}],
			}
		).insert(ignore_permissions=True, ignore_if_duplicate=True)

		remove_email_group_onboarding.execute()
		remove_email_group_onboarding.execute()

		for doctype in ("Onboarding Step", "Form Tour"):
			self.assertFalse(frappe.db.exists(doctype, remove_email_group_onboarding.NAME), doctype)

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

	def test_copied_function_schedules_move_to_their_own_dates_once(self):
		template = make_function("_Test Patch Template", start_date="2031-05-04")
		template.append("schedule", {"description": "Welcome", "start": "2031-05-04 10:00:00"})
		template.save(ignore_permissions=True)
		copy = make_function("_Test Patch Copy", start_date="2031-05-11", source_template=template.name)
		copy.append("schedule", {"description": "Welcome", "start": "2031-05-04 10:00:00"})
		copy.append("schedule", {"description": "Edited", "start": "2031-05-11 11:00:00"})
		copy.save(ignore_permissions=True)

		move_copied_function_schedules.execute()
		move_copied_function_schedules.execute()

		copy.reload()
		self.assertEqual(
			[str(row.start) for row in copy.schedule], ["2031-05-11 10:00:00", "2031-05-11 11:00:00"]
		)

	def test_starter_email_templates_get_the_html_body_they_were_sent_without(self):
		add_unsynced_default_records.execute()
		frappe.db.set_value(
			"Email Template", "Birthday Greeting", {"response": "<p>Old body</p>", "response_html": ""}
		)
		frappe.db.set_value(
			"Email Template",
			"Visitor Follow-Up",
			{"response": "<p>Old body</p>", "response_html": "<p>Ours</p>"},
		)

		move_email_template_bodies_to_html.execute()

		self.assertEqual(
			frappe.db.get_value("Email Template", "Birthday Greeting", "response_html"), "<p>Old body</p>"
		)
		self.assertEqual(
			frappe.db.get_value("Email Template", "Visitor Follow-Up", "response_html"), "<p>Ours</p>"
		)

	def test_ministry_teams_reach_the_portal_menu_and_email_templates_once(self):
		frappe.delete_doc_if_exists("Email Template", "Ministry Team Reminder")
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != add_ministry_teams.ROUTE]
		settings.save(ignore_permissions=True)

		add_ministry_teams.execute()
		add_ministry_teams.execute()

		routes = [row.route for row in frappe.get_doc("Portal Settings").menu]
		self.assertEqual(routes.count(add_ministry_teams.ROUTE), 1)
		self.assertIn(
			"{{ response_link }}",
			frappe.db.get_value("Email Template", "Ministry Team Reminder", "response_html"),
		)


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


class TestMoveToTheAppsScreenAndDock(RollbackEachTest):
	"""What Frappe's sidebar conversion made from Churchit's old navigation goes."""

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.clear_cache)
		frappe.db.set_single_value("Desktop Settings", "desktop_page", "Desktop Icons")
		frappe.get_doc(
			{"doctype": "Module Def", "module_name": "Manual: _Test", "app_name": "churchit", "custom": 1}
		).insert(ignore_permissions=True)
		self.converted_sidebar("_Test Manual", "Manual: _Test")
		self.converted_sidebar("_Test Merged", "Church Setup")
		frappe.db.delete("Dock", {"app": "churchit", "standard": 0})
		frappe.get_doc(
			{
				"doctype": "Dock",
				"app": "churchit",
				"items": [{"link_type": "Sidebar", "link_to": "_Test Manual"}],
			}
		).insert(ignore_permissions=True)
		administrator = frappe.get_doc("User", "Administrator")
		administrator.append("block_modules", {"module": "Church Missions"})
		administrator.append("block_modules", {"module": "Manual: _Test"})
		administrator.save(ignore_permissions=True)
		if not frappe.db.exists("Custom HTML Block", "WorkspaceHeader"):
			frappe.get_doc({"doctype": "Custom HTML Block", "html": "<nav></nav>"}).insert(
				set_name="WorkspaceHeader", ignore_permissions=True
			)

	def converted_sidebar(self, title, module):
		"""A site-owned sidebar as the conversion writes it, which only developer mode may save."""
		sidebar = frappe.get_doc(
			{
				"doctype": "Sidebar",
				"name": title,
				"title": title,
				"module": module,
				"merged_from": frappe.as_json([title]),
				"items": [{"type": "Link", "link_type": "DocType", "link_to": "Person", "label": "People"}],
			}
		)
		sidebar.db_insert()
		for item in sidebar.items:
			item.db_insert()

	def test_it_clears_the_conversion_and_opens_the_apps_screen(self):
		move_to_the_apps_screen_and_dock.execute()

		self.assertEqual(frappe.db.get_single_value("Desktop Settings", "desktop_page"), "Apps")
		self.assertFalse(frappe.db.exists("Module Def", "Manual: _Test"))
		self.assertFalse(frappe.db.exists("Sidebar", "_Test Manual"))
		self.assertFalse(frappe.db.exists("Sidebar", "_Test Merged"))
		self.assertFalse(frappe.db.exists("Dock", {"app": "churchit", "standard": 0}))
		self.assertFalse(
			frappe.db.exists("Block Module", {"parent": "Administrator", "module": "Church Missions"})
		)
		self.assertFalse(frappe.db.exists("Custom HTML Block", "WorkspaceHeader"))

	def test_it_keeps_the_sidebars_churchit_ships(self):
		move_to_the_apps_screen_and_dock.execute()

		self.assertTrue(frappe.db.exists("Sidebar", {"name": "People", "standard": 1}))
		self.assertTrue(frappe.db.exists("Dock", "churchit"))


class TestSplitMembershipFromMemberStatus(RollbackEachTest):
	"""Old Membership Status values become a Membership and an Active or Inactive status."""

	def setUp(self):
		super().setUp()
		for status in ("Active", "Inactive", "Visitor"):
			ensure("Member Status", {"status": status})
		ensure("Membership Type", {"type": "Visitor"})
		ensure("Life Event Type", {"type": "Membership"})

	def old_person(self, first_name, status=None, **values):
		person = make_person(first_name, "_Test Split", **values)
		frappe.db.set_value("Person", person.name, {"membership": None, "membership_status": status})
		return person.name

	def after_patch(self, name):
		split_membership_from_member_status.execute()
		return frappe.db.get_value("Person", name, ["membership", "membership_status"])

	def test_a_person_with_a_membership_event_becomes_an_active_member(self):
		name = self.old_person("Joined", life_events=[{"event_type": "Membership", "date": "2010-01-01"}])
		self.assertEqual(self.after_patch(name), ("Member", "Active"))

	def test_an_inactive_member_stays_inactive(self):
		self.assertEqual(self.after_patch(self.old_person("Lapsed", "Inactive")), ("Member", "Inactive"))

	def test_a_status_named_like_a_membership_type_moves_to_membership(self):
		self.assertEqual(self.after_patch(self.old_person("Guest", "Visitor")), ("Visitor", "Active"))

	def test_a_person_without_a_status_becomes_active_with_no_membership(self):
		self.assertEqual(self.after_patch(self.old_person("Unknown")), (None, "Active"))

	def test_a_copied_notification_gets_the_new_condition(self):
		notification = frappe.get_doc(
			{
				"doctype": "Notification",
				"name": "_Test Copied Welcome",
				"subject": "Welcome",
				"document_type": "Person",
				"event": "Value Change",
				"value_changed": "membership_status",
				"condition": 'doc.membership_status == "Active" and doc.emails',
				"channel": "System Notification",
				"recipients": [{"receiver_by_role": "System Manager"}],
				"enabled": 0,
			}
		).insert(ignore_permissions=True)

		split_membership_from_member_status.execute()

		notification.reload()
		self.assertEqual(notification.value_changed, "membership")
		self.assertEqual(
			notification.condition,
			'doc.membership == "Member" and doc.membership_status == "Active" and doc.emails',
		)


class TestSetChurchWebsite(RollbackEachTest):
	"""The directory cover keeps the site address it printed before the Website field."""

	def setUp(self):
		super().setUp()
		self.church = ensure_root_church()
		frappe.db.set_value("Church", self.church, "website", None)

	def set_website_feature(self, enabled):
		frappe.db.set_single_value("Church Features", "enable_website", enabled)

	def test_the_site_address_fills_an_empty_website(self):
		self.set_website_feature(1)
		set_church_website.execute()
		self.assertEqual(frappe.db.get_value("Church", self.church, "website"), frappe.utils.get_url())

	def test_a_church_without_the_web_site_module_keeps_no_website(self):
		self.set_website_feature(0)
		set_church_website.execute()
		self.assertIsNone(frappe.db.get_value("Church", self.church, "website"))

	def test_a_website_the_church_set_is_kept(self):
		self.set_website_feature(1)
		frappe.db.set_value("Church", self.church, "website", "https://ours.example.org")
		set_church_website.execute()
		self.assertEqual(frappe.db.get_value("Church", self.church, "website"), "https://ours.example.org")


class TestAddMissionaryStatuses(RollbackEachTest):
	"""Existing missionaries get a Status from whether their support has ended."""

	def test_ended_support_is_inactive_and_the_rest_active(self):
		current = frappe.get_doc({"doctype": "Missionary", "title": "_Test Current Missionary"}).insert(
			ignore_permissions=True
		)
		ended = frappe.get_doc(
			{"doctype": "Missionary", "title": "_Test Ended Missionary", "support_end_date": "2020-01-01"}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Missionary", {"name": ("in", [current.name, ended.name])}, "status", None)

		add_missionary_statuses.execute()

		self.assertEqual(frappe.db.get_value("Missionary", current.name, "status"), "Active")
		self.assertEqual(frappe.db.get_value("Missionary", ended.name, "status"), "Inactive")
		self.assertTrue(frappe.db.exists("Missionary Status", "Pending"))


class TestAddMaritalStatuses(RollbackEachTest):
	"""Everyone ticked Is Married becomes Married, and nobody else gets a status."""

	def test_ticked_people_become_married(self):
		if not frappe.db.has_column("Person", "is_married"):
			self.skipTest("this site never had the Is Married column")
		married = make_person("_Test Patch", "Ticked")
		unticked = make_person("_Test Patch", "Unticked")
		Person = frappe.qb.DocType("Person")
		frappe.qb.update(Person).set(Person.is_married, 1).where(Person.name == married.name).run()

		add_marital_statuses.execute()
		add_marital_statuses.execute()

		self.assertEqual(frappe.db.get_value("Person", married.name, "marital_status"), "Married")
		self.assertIsNone(frappe.db.get_value("Person", unticked.name, "marital_status"))
		self.assertTrue(frappe.db.exists("Marital Status", "Widowed"))


class TestReplaceHeadOfHouseholdWithPrimaryContact(RollbackEachTest):
	"""The head of household becomes the Primary Contact, and Relations rows fill blank relationships."""

	def setUp(self):
		super().setUp()
		if not frappe.db.has_column("Person", "is_head_of_household") or not frappe.db.table_exists(
			"Person Relation"
		):
			self.skipTest("this site never had heads of household or the Relations table")

	def add_relation(self, person, other, relation_type):
		Relation = frappe.qb.DocType("Person Relation")
		frappe.qb.into(Relation).columns(
			Relation.name,
			Relation.parent,
			Relation.parenttype,
			Relation.parentfield,
			Relation.person,
			Relation.type,
		).insert(frappe.generate_hash(length=10), person, "Person", "relations", other, relation_type).run()

	def test_the_head_becomes_primary_contact_and_relations_fill_blank_relationships(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Patch - Pat"}).insert(
			ignore_permissions=True
		)
		pat = make_person("_Test Pat", "Patch", gender="Male", family=family.name)
		pam = make_person(
			"_Test Pam",
			"Patch",
			gender="Female",
			family=family.name,
			spouse=pat.name,
			marital_status="Married",
		)
		sid = make_person("_Test Sid", "Patch", gender="Male", family=family.name)
		meg = make_person("_Test Meg", "Patch", gender="Female", family=family.name)
		cousin = make_person("_Test Cy", "Elsewhere", gender="Male")
		Person = frappe.qb.DocType("Person")
		frappe.qb.update(Person).set(Person.is_head_of_household, 1).where(Person.name == pat.name).run()
		self.add_relation(pat.name, sid.name, "Son")
		self.add_relation(meg.name, pat.name, "Son")
		self.add_relation(pat.name, cousin.name, "Cousin")

		primary_contact_patch.execute()
		primary_contact_patch.execute()

		self.assertEqual(frappe.db.get_value("Family", family.name, "primary_contact"), pat.name)
		labels = {
			member.member: member.relationship_to_primary_contact
			for member in frappe.get_doc("Family", family.name).members
		}
		self.assertEqual(labels, {pat.name: "Husband", pam.name: "Wife", sid.name: "Son", meg.name: "Mother"})

	def test_copied_notifications_read_the_primary_contact(self):
		frappe.db.set_value(
			"Notification", "Anniversary Greeting", "condition", "doc.emails and doc.is_head_of_household"
		)

		primary_contact_patch.execute()

		self.assertEqual(
			frappe.db.get_value("Notification", "Anniversary Greeting", "condition"),
			"doc.emails and doc.is_primary_contact",
		)


class TestPersonProfilePatches(RollbackEachTest):
	def test_existing_people_get_the_display_name_they_go_by(self):
		person = make_person("_Test Robert", "Patch", nickname="Bob", suffix="Jr.")
		frappe.db.set_value("Person", person.name, "display_name", None, update_modified=False)

		set_display_names.execute()

		self.assertEqual(frappe.db.get_value("Person", person.name, "display_name"), "Bob Patch Jr.")

	def test_existing_people_have_no_source_rather_than_a_guessed_one(self):
		"""The new column gave everyone its default, Desk, though nobody knows how they were added."""
		person = make_person("_Test Unknown", "Source")
		self.assertEqual(person.source, "Desk")

		clear_unknown_person_sources.execute()

		self.assertIsNone(frappe.db.get_value("Person", person.name, "source"))


class TestRemoveAveryLabelFormat(RollbackEachTest):
	def test_the_format_and_a_family_default_naming_it_are_removed(self):
		name = remove_avery_label_format.AVERY_LABELS
		if not frappe.db.exists("Print Format", name):
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": name,
					"doc_type": "Family",
					"module": "Church People",
					"standard": "No",
					"custom_format": 1,
					"print_format_type": "Jinja",
					"html": "<div>{{ doc.family_name }}</div>",
				}
			).insert(ignore_permissions=True)
		make_property_setter("Family", None, "default_print_format", name, "Data", for_doctype=True)

		remove_avery_label_format.execute()

		self.assertFalse(frappe.db.exists("Print Format", name))
		self.assertFalse(frappe.db.exists("Property Setter", {"doc_type": "Family", "value": name}))


class TestMarkCheckInWalkInsAsVisitors(RollbackEachTest):
	def test_a_walk_in_becomes_a_visitor_who_shares_nothing(self):
		walk_in = make_person("_Test Walk", "In", source="Check-In", membership=None, share_phone=1)
		member = make_person("_Test Walk", "Member", source="Check-In", membership="Member", share_phone=1)
		login = ensure_user("_test_walk_in_login@example.com", "WalkInLogin")
		chose = make_person(
			"_Test Walk", "Chose", source="Check-In", membership=None, share_phone=1, user=login
		)

		mark_check_in_walk_ins_as_visitors.execute()

		def state(person):
			return frappe.db.get_value("Person", person.name, ["membership", "share_phone"])

		self.assertEqual(state(walk_in), ("Visitor", 0))
		self.assertEqual(state(member), ("Member", 1))
		self.assertEqual(state(chose), (None, 1), "a portal login may have chosen to share")


class TestRestampSharedFundTransfers(RollbackEachTest):
	def test_a_shared_transfer_takes_the_church_of_whoever_made_it(self):
		church = ensure_root_church()
		transfer = frappe.get_doc(
			{"doctype": "Fund Transfer", "from_fund": "_Test Shared", "to_fund": "_Test Own", "amount": 1}
		)
		transfer.db_insert()
		with (
			mock.patch.object(restamp_shared_fund_transfers, "is_multi_church", return_value=True),
			mock.patch.object(restamp_shared_fund_transfers, "default_church", return_value=church) as maker,
		):
			restamp_shared_fund_transfers.execute()

		self.assertEqual(frappe.db.get_value("Fund Transfer", transfer.name, "church"), church)
		maker.assert_any_call(transfer.owner)


class TestRemovePrivateFieldsFromVersions(RollbackEachTest):
	def test_private_changes_leave_the_versions_once(self):
		def version(ref_doctype, **diff):
			return frappe.get_doc(
				{
					"doctype": "Version",
					"ref_doctype": ref_doctype,
					"docname": "_Test Private Fields",
					"data": frappe.as_json(
						{"changed": [], "added": [], "removed": [], "row_changed": [], **diff}
					),
				}
			).insert(ignore_permissions=True)

		pickup = ["authorized_pickups", {"person": "PRSN-X", "notes": "_Test gate code"}]
		mixed = version("Family", changed=[["family_name", "Old", "New"]], added=[pickup])
		only_pickups = version("Family", removed=[pickup], row_changed=[["authorized_pickups", 0, "row", []]])
		key = ["team_calendar_key", None, "_test_key"]
		merged = version("Person", changed=[key, ["gender", "Unknown", "Female"]])
		only_key = version("Person", changed=[key])

		remove_private_fields_from_versions.execute()
		remove_private_fields_from_versions.execute()

		data = frappe.parse_json(frappe.db.get_value("Version", mixed.name, "data"))
		self.assertEqual((data.changed, data.added), ([["family_name", "Old", "New"]], []))
		self.assertFalse(frappe.db.exists("Version", only_pickups.name))
		data = frappe.parse_json(frappe.db.get_value("Version", merged.name, "data"))
		self.assertEqual(data.changed, [["gender", "Unknown", "Female"]])
		self.assertFalse(frappe.db.exists("Version", only_key.name))


class TestRemovePermlevelFieldsFromPersonVersions(RollbackEachTest):
	def test_medical_notes_leave_the_person_versions_once(self):
		def version(*changed):
			return frappe.get_doc(
				{
					"doctype": "Version",
					"ref_doctype": "Person",
					"docname": "_Test Medical Versions",
					"data": frappe.as_json(
						{"changed": list(changed), "added": [], "removed": [], "row_changed": []}
					),
				}
			).insert(ignore_permissions=True)

		notes = ["medical_notes", None, "_Test Diabetic"]
		renamed = version(notes, ["first_name", "Old", "New"])
		only_notes = version(notes, ["open_care_requests", 0, 1])

		remove_permlevel_fields_from_person_versions.execute()
		remove_permlevel_fields_from_person_versions.execute()

		data = frappe.parse_json(frappe.db.get_value("Version", renamed.name, "data"))
		self.assertEqual(data.changed, [["first_name", "Old", "New"]])
		self.assertFalse(frappe.db.exists("Version", only_notes.name))
