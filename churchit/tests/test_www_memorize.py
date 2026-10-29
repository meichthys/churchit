# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError, ValidationError

from churchit.tests.helpers import RollbackEachTest, ensure_user, make_translation
from churchit.www.memorize import index, session


class TestMemorizePages(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.translation = make_translation(cls, "_TPG", [("GEN", 1, 1, "In the beginning God created.")])
		cls.user = ensure_user("_test_page_learner@example.com", "_Test Page Learner")
		cls.other = ensure_user("_test_page_other@example.com", "_Test Page Other")
		frappe.db.delete("Bible Memory Item", {"translation": cls.translation})
		cls.item = frappe.get_doc(
			{
				"doctype": "Bible Memory Item",
				"bible_reference": "Genesis 1:1",
				"translation": cls.translation,
				"user": cls.user,
				"assigned_by": cls.other,
				"progress": 40,
				"word_mistakes": {"2": 1},
			}
		).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		frappe.set_user(self.user)
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		super().tearDown()
		frappe.local.form_dict = frappe._dict()

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		for page in (index, session):
			with self.assertRaises(frappe.Redirect):
				page.get_context(frappe._dict())
			self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/memorize")

	def test_index_lists_the_users_items_with_labels(self):
		context = frappe._dict()
		index.get_context(context)

		items = {item["name"]: item for item in context["items"]}
		self.assertIn(self.item.name, items)
		self.assertEqual(items[self.item.name]["label"], "Genesis 1:1 (_TPG)")
		self.assertEqual(items[self.item.name]["assigned_by_label"], "_Test Page Other")
		self.assertIn(self.translation, [translation.name for translation in context["translations"]])

	def test_index_offers_the_groups_of_the_users_items(self):
		group = frappe.get_doc({"doctype": "Group", "group_name": "_Test Page Memory Group"})
		group = group.insert(ignore_permissions=True).name
		frappe.db.set_value("Bible Memory Item", self.item.name, "group", group)

		context = frappe._dict()
		index.get_context(context)
		self.assertEqual(context.groups, {group: "_Test Page Memory Group"})
		self.assertEqual([item["group"] for item in context["items"]], [group])

	def test_index_offers_no_group_filter_without_groups(self):
		context = frappe._dict()
		index.get_context(context)
		self.assertEqual(context.groups, {})

	def test_index_hides_other_users_items(self):
		frappe.set_user(self.other)
		context = frappe._dict()
		index.get_context(context)
		self.assertNotIn(self.item.name, [item["name"] for item in context["items"]])

	def test_session_context_carries_the_passage_and_progress(self):
		frappe.local.form_dict = frappe._dict(item=self.item.name, mode="BLUR")
		context = frappe._dict()
		session.get_context(context)

		self.assertEqual(context.item_name, self.item.name)
		self.assertEqual(context.mode, "blur")
		self.assertEqual(context.progress, 40)
		self.assertEqual(context.reference_label, "Genesis 1:1 (_TPG)")
		self.assertEqual(context.reference_text, "1 In the beginning God created.")
		self.assertEqual(frappe.parse_json(context.word_mistakes_json), {"2": 1})
		self.assertTrue(context.no_header)

	def test_session_explains_a_translation_without_text(self):
		frappe.db.set_value("Bible Translation", self.translation, "status", "Downloading")
		frappe.local.form_dict = frappe._dict(item=self.item.name)
		with self.assertRaisesRegex(ValidationError, "no text"):
			session.get_context(frappe._dict())

	def test_session_rejects_bad_mode_missing_item_and_other_users(self):
		frappe.local.form_dict = frappe._dict(item=self.item.name, mode="listen")
		with self.assertRaises(ValidationError):
			session.get_context(frappe._dict())

		frappe.local.form_dict = frappe._dict(mode="type")
		with self.assertRaises(ValidationError):
			session.get_context(frappe._dict())

		frappe.set_user(self.other)
		frappe.local.form_dict = frappe._dict(item=self.item.name)
		with self.assertRaises(PermissionError):
			session.get_context(frappe._dict())
