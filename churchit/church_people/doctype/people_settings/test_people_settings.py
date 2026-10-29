# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.derived import refresh_daily
from churchit.church_people.doctype.people_settings.people_settings import (
	DIRECTORY_ROUTE,
	store_defaults,
	sync_directory_menu_item,
)
from churchit.patches.v1_0 import apply_directory_share_defaults
from churchit.tests.helpers import RollbackEachTest, make_person


def save_adult_age(age):
	settings = frappe.get_single("People Settings")
	settings.adult_age = age
	settings.save(ignore_permissions=True)


class TestPeopleSettings(FrappeTestCase):
	def test_a_site_that_never_saved_the_settings_gets_the_default_adult_age(self):
		"""A Single nobody saved stores nothing, so a reader got 0 and everyone with an age was an Adult."""
		frappe.db.delete("Singles", {"doctype": "People Settings"})

		store_defaults()

		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 18)

	def test_storing_the_defaults_keeps_a_saved_adult_age(self):
		save_adult_age(21)

		store_defaults()

		self.assertEqual(frappe.db.get_single_value("People Settings", "adult_age"), 21)

	def test_changing_the_adult_age_rechecks_every_life_stage(self):
		save_adult_age(18)
		settings = frappe.get_single("People Settings")

		with patch("frappe.enqueue") as enqueue:
			settings.save(ignore_permissions=True)
			enqueue.assert_not_called()

			settings.adult_age = 16
			settings.save(ignore_permissions=True)

		enqueue.assert_called_once_with(refresh_daily, enqueue_after_commit=True)


def save_settings(**values):
	settings = frappe.get_single("People Settings")
	settings.update(values)
	settings.save(ignore_permissions=True)


def directory_menu_rows():
	return [row for row in frappe.get_single("Portal Settings").menu if row.route == DIRECTORY_ROUTE]


class TestMemberDirectorySettings(RollbackEachTest):
	def test_new_people_share_what_the_settings_say_and_people_on_file_keep_their_choice(self):
		save_settings(
			directory_share_email=0,
			directory_share_phone=0,
			directory_share_address=0,
			directory_share_birthday=0,
		)
		on_file = make_person("_Test Sharing", "On File").name

		save_settings(
			directory_share_email=1,
			directory_share_phone=0,
			directory_share_address=1,
			directory_share_birthday=1,
		)
		# Frappe keeps a new record's defaults until the request ends, and the next request starts afresh.
		frappe.local.new_doc_templates.pop("Person", None)
		newcomer = make_person("_Test Sharing", "Newcomer").name

		shares = ["share_email", "share_phone", "share_address", "share_birthday"]
		self.assertEqual(frappe.db.get_value("Person", newcomer, shares), (1, 0, 1, 1))
		self.assertEqual(frappe.db.get_value("Person", on_file, shares), (0, 0, 0, 0))

	def test_the_patch_follows_sharing_that_migrate_stored_without_a_save(self):
		frappe.db.set_single_value(
			"People Settings", {"directory_share_email": 1, "directory_share_address": 0}
		)

		apply_directory_share_defaults.execute()

		meta = frappe.get_meta("Person")
		self.assertEqual(meta.get_field("share_email").default, "1")
		self.assertEqual(meta.get_field("share_address").default, "0")

	def test_saving_unchanged_sharing_writes_no_property_setter(self):
		save_settings(directory_share_email=1)
		setters = frappe.get_all(
			"Property Setter", filters={"doc_type": "Person"}, fields=["name", "modified"]
		)

		save_settings(adult_age=frappe.db.get_single_value("People Settings", "adult_age"))

		self.assertEqual(
			frappe.get_all("Property Setter", filters={"doc_type": "Person"}, fields=["name", "modified"]),
			setters,
		)

	def test_the_member_directory_shows_in_the_portal_menu_only_while_it_is_on(self):
		frappe.db.delete("Portal Menu Item", {"parent": "Portal Settings", "route": DIRECTORY_ROUTE})
		frappe.get_doc(
			{
				"doctype": "Portal Menu Item",
				"parenttype": "Portal Settings",
				"parent": "Portal Settings",
				"parentfield": "menu",
				"idx": 99,
				"title": "Member Directory",
				"route": DIRECTORY_ROUTE,
				"reference_doctype": "Person",
				"role": "Church User",
				"enabled": 1,
			}
		).db_insert()
		frappe.db.set_single_value("People Settings", "member_directory", 0)

		sync_directory_menu_item()
		self.assertEqual([row.enabled for row in directory_menu_rows()], [0])

		save_settings(member_directory=1)
		self.assertEqual([row.enabled for row in directory_menu_rows()], [1])
