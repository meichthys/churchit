# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure, ensure_user
from churchit.www.memorize import index, session


class TestMemorizePages(FrappeTestCase):
	def setUp(self):
		book = ensure(
			"Bible Book", {"book": "_Test Page Book"}, {"book": "_Test Page Book", "abbreviation": "TPB"}
		)
		verse = ensure("Bible Verse", {"name": f"{book} 1:1"}, {"book": book, "chapter": 1, "verse": 1})
		self.reference = ensure(
			"Bible Reference", {"start_verse": verse, "end_verse": ["is", "not set"]}, {"start_verse": verse}
		)
		frappe.db.set_value("Bible Reference", self.reference, "reference_text", "1. In the beginning")
		self.user = ensure_user("_test_page_learner@example.com", "_Test Page Learner")
		self.other = ensure_user("_test_page_other@example.com", "_Test Page Other")
		frappe.db.delete("Bible Memory Item", {"bible_reference": self.reference})
		self.item = frappe.get_doc(
			{
				"doctype": "Bible Memory Item",
				"bible_reference": self.reference,
				"user": self.user,
				"assigned_by": self.other,
				"progress": 40,
				"word_mistakes": {"2": 1},
			}
		).insert(ignore_permissions=True)
		frappe.set_user(self.user)
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.set_user("Administrator")
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
		self.assertEqual(items[self.item.name]["label"], "_Test Page Book 1:1")
		self.assertEqual(items[self.item.name]["assigned_by_label"], "_Test Page Other")
		self.assertTrue(context["books"])
		self.assertTrue(context["translations"])

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
		self.assertEqual(context.reference_label, "_Test Page Book 1:1")
		self.assertEqual(context.reference_text, "1. In the beginning")
		self.assertEqual(frappe.parse_json(context.word_mistakes_json), {"2": 1})
		self.assertTrue(context.no_header)

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
