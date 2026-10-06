# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit import scripture
from churchit.tests.helpers import make_translation
from churchit.www import bible

TEXT = [
	("GEN", 1, 1, "In the beginning God created."),
	("GEN", 2, 1, "Thus the heavens were completed."),
	("EXO", 1, 1, "These are the names."),
]


class TestBiblePage(FrappeTestCase):
	def setUp(self):
		self.free = make_translation(self, "_TBF", TEXT, free=True)
		self.imported = make_translation(self, "_TBI", TEXT)
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def context(self, **query):
		frappe.local.form_dict = frappe._dict(query)
		context = frappe._dict()
		with patch.object(scripture, "get_default_translation", return_value=self.free):
			bible.get_context(context)
		return context

	def test_opens_the_default_translation_at_its_first_chapter(self):
		context = self.context()
		self.assertEqual(
			(context.translation.name, context.book["id"], context.chapter), (self.free, "GEN", 1)
		)
		self.assertEqual(context.content[0]["text"], "In the beginning God created.")
		self.assertIsNone(context.previous_url)
		self.assertEqual(context.next_url, f"/bible?translation={self.free}&book=GEN&chapter=2")

	def test_only_members_get_the_portal_sidebar(self):
		self.assertTrue(self.context().show_sidebar)
		frappe.set_user("Guest")
		self.assertFalse(self.context().show_sidebar)

	def test_the_next_chapter_runs_on_into_the_next_book(self):
		context = self.context(translation=self.free, book="gen", chapter="2")
		self.assertEqual(context.next_url, f"/bible?translation={self.free}&book=EXO&chapter=1")
		self.assertEqual(context.previous_url, f"/bible?translation={self.free}&book=GEN&chapter=1")

	def test_an_unknown_book_or_chapter_falls_back_to_one_that_exists(self):
		context = self.context(translation=self.free, book="TOB", chapter="99")
		self.assertEqual((context.book["id"], context.chapter), ("GEN", 2))

	def test_links_keep_the_chosen_church(self):
		context = self.context(translation=self.free, church="CHR-01")
		self.assertEqual(context.next_url, f"/bible?translation={self.free}&book=GEN&chapter=2&church=CHR-01")

	def test_guests_cannot_open_an_imported_text(self):
		frappe.set_user("Guest")
		context = self.context(translation=self.imported)
		self.assertEqual(context.translation.name, self.free)
		self.assertNotIn(self.imported, [translation.name for translation in context.translations])

	def test_the_page_shows_the_chapter_and_its_pickers(self):
		html = self.serve(translation=self.free, book="GEN", chapter="2")
		self.assertIn("Thus the heavens were completed.", html)
		self.assertIn('<option value="EXO"', html)

	def test_nothing_to_read_says_so(self):
		with patch.object(bible, "get_readable_translations", return_value=[]):
			html = self.serve()
		self.assertIn("No Bible translation is ready to read yet.", html)

	def serve(self, **query):
		frappe.local.form_dict = frappe._dict(query)
		set_request(method="GET", path="bible")
		with patch.object(scripture, "get_default_translation", return_value=self.free):
			return get_response("bible").get_data(as_text=True)
