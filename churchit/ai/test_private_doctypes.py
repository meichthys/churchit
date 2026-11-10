# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Only for Local or Zero Retention Models on Church AI Settings: what it recommends, how it fills,
who may shorten it, and the warning when a recommended doctype goes."""

import frappe

from churchit.ai.flow_switch import forget_missing_blocked_doctypes
from churchit.ai.private_doctypes import (
	RECOMMENDED,
	fill_private_doctypes,
	get_private_doctypes,
	use_recommended_private_doctypes,
)
from churchit.ai.switch import SETTINGS
from churchit.church_foundations.church_access import set_user_church
from churchit.patches.v1_0 import fill_private_model_doctypes
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches

MANAGER = "_test_private_list_manager@example.com"
BRANCH_MANAGER = "_test_private_list_branch_manager@example.com"
STAFF = "_test_private_list_staff@example.com"


def set_rows(*doctypes: str):
	settings = frappe.get_single(SETTINGS)
	settings.private_model_doctypes = []
	for doctype in doctypes:
		settings.append("private_model_doctypes", {"document_type": doctype})
	settings.save()
	return settings


def get_rows() -> list[str]:
	return [row.document_type for row in frappe.get_single(SETTINGS).private_model_doctypes]


class TestRecommendedList(RollbackEachTest):
	def test_each_recommended_doctype_is_a_churchit_doctype_with_records_of_its_own(self):
		for doctype in RECOMMENDED:
			with self.subTest(doctype):
				meta = frappe.get_meta(doctype)
				self.assertEqual(frappe.db.get_value("Module Def", meta.module, "app_name"), "churchit")
				self.assertFalse(meta.istable or meta.issingle)

	def test_people_and_church_emails_are_not_recommended(self):
		"""Writer, with No training, may get them."""
		self.assertNotIn("Person", RECOMMENDED)
		self.assertNotIn("Church Email", RECOMMENDED)

	def test_fill_starts_an_empty_list_and_keeps_a_list_with_rows(self):
		set_rows()
		fill_private_doctypes()
		self.assertEqual(get_rows(), list(RECOMMENDED))
		self.assertEqual(get_private_doctypes(), set(RECOMMENDED))

		set_rows("Prayer Request")
		fill_private_doctypes()
		self.assertEqual(get_rows(), ["Prayer Request"])

	def test_a_missing_doctype_loses_its_row(self):
		"""A migrate or an uninstall deletes doctypes without checking links."""
		settings = set_rows("Care Request")
		row = settings.append("private_model_doctypes", {"document_type": "_Test Gone DocType"})
		row.db_insert()

		forget_missing_blocked_doctypes()
		self.assertEqual(get_rows(), ["Care Request"])

	def test_the_patch_fills_the_list_on_a_site_with_a_row_of_a_missing_doctype(self):
		"""The patch runs before after_migrate deletes such a row, which fails the save."""
		settings = set_rows()
		row = settings.append("blocked_knowledge_doctypes", {"document_type": "_Test Gone DocType"})
		row.db_insert()

		fill_private_model_doctypes.execute()
		self.assertEqual(get_rows(), list(RECOMMENDED))


class TestWhoChangesTheList(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, branch, _other = make_two_churches()
		ensure_user(MANAGER, "Private List Manager", roles=("Church Manager",))
		frappe.db.delete("User Permission", {"user": MANAGER, "allow": "Church"})
		ensure_user(BRANCH_MANAGER, "Private List Branch Manager", roles=("Church Manager",))
		set_user_church(BRANCH_MANAGER, branch)
		ensure_user(STAFF, "Private List Staff", roles=("Church Staff",))
		frappe.clear_cache(user=MANAGER)

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, {"enabled": 0, "acknowledged": 0})

	def test_the_button_adds_what_is_missing_keeps_every_row_and_works_while_ai_is_off(self):
		set_rows("Prayer Request", "Function")
		frappe.set_user(MANAGER)

		self.assertEqual(use_recommended_private_doctypes(), len(RECOMMENDED) - 1)
		self.assertEqual(set(get_rows()), {*RECOMMENDED, "Function"})
		self.assertEqual(use_recommended_private_doctypes(), 0)

	def test_only_managers_use_the_button(self):
		frappe.set_user(STAFF)
		self.assertRaises(frappe.PermissionError, use_recommended_private_doctypes)

	def test_removing_a_recommended_doctype_saves_with_an_orange_warning(self):
		set_rows("Care Request", "Function")
		frappe.set_user(MANAGER)
		frappe.local.message_log = []

		set_rows("Function")

		self.assertEqual(get_rows(), ["Function"])
		[warning] = [frappe.parse_json(message) for message in frappe.local.message_log]
		self.assertEqual(warning["indicator"], "orange")
		self.assertIn("Care Request", warning["message"])

	def test_a_branch_church_manager_can_add_a_doctype_but_not_remove_one(self):
		"""Removing one loosens the list for every church, as turning AI on does."""
		set_rows("Care Request")
		frappe.set_user(BRANCH_MANAGER)
		set_rows("Care Request", "Function")

		self.assertRaisesRegex(frappe.PermissionError, "remove a DocType", set_rows, "Function")
