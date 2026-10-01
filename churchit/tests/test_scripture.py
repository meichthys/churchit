# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit import scripture
from churchit.tests.helpers import ensure_root_church, ensure_user, make_translation

JOHN = [
	("JHN", 3, 16, "For God so loved the world."),
	("John", 3, 17, "For God did not send His Son to condemn the world."),
	("JHN", 4, 1, "Now Jesus learned that the Pharisees had heard."),
]
PSALM = [("Psalms", 23, 1, "The LORD is my shepherd;\nI shall not want.")]


class TestReferences(FrappeTestCase):
	def test_typed_references_are_tidied_for_storage(self):
		self.assertEqual(scripture.format_reference("rom 8:28-30;ps 23"), "Romans 8:28-30; Psalms 23")
		self.assertEqual(scripture.format_reference("jn 3:16,18"), "John 3:16; John 3:18")
		self.assertEqual(scripture.format_reference("Jude 1:3"), "Jude 3")
		self.assertEqual(scripture.format_reference("Psalms 23:1 - Psalms 23:6 (KJV)"), "Psalms 23:1-6")
		self.assertIsNone(scripture.format_reference(None))
		self.assertEqual(scripture.format_reference(""), "")

	def test_a_whole_chapter_or_book_is_kept_short_not_expanded_into_verses(self):
		"""pythonbible's own formatter writes "Psalms 23:1-6"; what the user typed stays a chapter."""
		self.assertEqual(scripture.format_reference("Ps 23"), "Psalms 23")
		self.assertEqual(scripture.format_reference("Gen 1-2"), "Genesis 1-2")
		self.assertEqual(scripture.format_reference("Genesis - Exodus"), "Genesis - Exodus")
		self.assertEqual(scripture.format_reference("Jude"), "Jude")

	def test_several_passages_keep_the_order_they_were_typed_in(self):
		"""pythonbible's formatter sorts multiple passages into Bible order; this does not."""
		self.assertEqual(scripture.format_reference("jn 3:16; gen 1:1"), "John 3:16; Genesis 1:1")
		self.assertEqual(scripture.format_reference("eph 2:8-9;rom 3:23"), "Ephesians 2:8-9; Romans 3:23")

	def test_unknown_and_deuterocanonical_passages_are_refused(self):
		for text in ("not a verse", "John 30:1", "Tobit 1:1"):
			with self.assertRaises(frappe.ValidationError, msg=text):
				scripture.parse_reference(text)

	def test_verses_are_grouped_by_chapter_in_reading_order(self):
		self.assertEqual(
			scripture.get_verses_by_chapter("John 3:35-4:2"),
			{("JHN", 3): [35, 36], ("JHN", 4): [1, 2]},
		)


class TestTextFiles(FrappeTestCase):
	def test_csv_names_books_by_id_or_by_name(self):
		books = scripture._from_csv("Book,Chapter,Verse,Text\nJHN,3,16,For God\n1 Cor,13,4,Love is patient\n")
		self.assertEqual((books["JHN"]["name"], books["1CO"]["name"]), ("John", "1 Corinthians"))
		self.assertEqual(
			books["1CO"]["chapters"][13], [{"type": "verse", "number": 4, "text": "Love is patient"}]
		)
		self.assertEqual(scripture.count_verses(books), 2)

	def test_csv_needs_its_columns_whole_rows_and_known_books(self):
		with self.assertRaisesRegex(frappe.ValidationError, "needs the columns"):
			scripture._from_csv("book,text\nJHN,x\n")
		with self.assertRaisesRegex(frappe.ValidationError, "Line 3"):
			scripture._from_csv("book,chapter,verse,text\nJHN,3,16,x\nJHN,three,17,y\n")
		with self.assertRaisesRegex(frappe.ValidationError, "Hezekiah"):
			scripture._from_csv("book,chapter,verse,text\nHezekiah,1,1,x\n")

	def test_free_use_json_keeps_each_chapter_as_published(self):
		content = [{"type": "heading", "text": "The Creation"}, {"type": "verse", "number": 1, "text": "In"}]
		books = scripture.from_free_use_json(free_use_bible([("GEN", "Genesis", 1, content)]))
		self.assertEqual(books, {"GEN": {"name": "Genesis", "chapters": {1: content}}})

	def test_a_download_leaves_out_the_audio(self):
		data = free_use_bible([("GEN", "Genesis", 1, [])])
		data["books"][0]["chapters"][0].update(thisChapterAudioLinks={"a": "x"}, thisChapterAudioTimings={})
		response = MagicMock(json=MagicMock(return_value=data))
		with patch("churchit.scripture.requests.get", return_value=response) as get:
			chapter = scripture.download_free_use_bible("BSB")["books"][0]["chapters"][0]
		self.assertEqual(
			get.call_args.args[0], f"{scripture.FREE_USE_BIBLE_API_URL}/BSB/complete.simple.json"
		)
		self.assertNotIn("thisChapterAudioLinks", chapter)
		self.assertNotIn("thisChapterAudioTimings", chapter)


class TestReading(FrappeTestCase):
	def setUp(self):
		self.free = make_translation(self, "_TSF", JOHN + PSALM, free=True)
		self.imported = make_translation(self, "_TSI", JOHN)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_books_and_chapters_come_from_the_text(self):
		self.assertEqual(
			scripture.get_books(self.free),
			[{"id": "JHN", "name": "John", "chapters": 2}, {"id": "PSA", "name": "Psalms", "chapters": 1}],
		)
		self.assertEqual([item["number"] for item in scripture.get_chapter("jhn", 3, self.free)], [16, 17])
		self.assertEqual(scripture.get_chapter("JHN", 99, self.free), [])

	def test_a_passage_spans_chapters_and_leaves_out_verses_the_text_lacks(self):
		passage = scripture.get_passage("John 3:16-4:1", self.free)
		self.assertEqual(
			[(section["chapter"], len(section["verses"])) for section in passage], [(3, 2), (4, 1)]
		)

	def test_passage_text_is_one_numbered_line(self):
		self.assertEqual(
			scripture.get_passage_text("Psalms 23:1", self.free),
			"1 The LORD is my shepherd; I shall not want.",
		)

	def test_guests_read_only_free_texts(self):
		frappe.set_user("Guest")
		self.assertTrue(scripture.get_chapter("JHN", 3, self.free))
		with self.assertRaises(frappe.PermissionError):
			scripture.get_chapter("JHN", 3, self.imported)
		readable = [translation.name for translation in scripture.get_readable_translations()]
		self.assertIn(self.free, readable)
		self.assertNotIn(self.imported, readable)

	def test_members_read_their_churchs_imported_texts(self):
		frappe.set_user(ensure_user("_test_bible_reader@example.com", "_Test Reader"))
		self.assertTrue(scripture.get_chapter("JHN", 3, self.imported))

	def test_a_translation_without_its_text_cannot_be_read(self):
		frappe.db.set_value("Bible Translation", self.free, "status", "Downloading")
		self.assertFalse(scripture.is_readable(self.free))
		self.assertFalse(scripture.is_readable(None))
		with self.assertRaises(frappe.PermissionError):
			scripture.get_books(self.free)

	def test_saving_a_translation_drops_its_cached_text(self):
		scripture.get_books(self.free)
		self.assertIsNotNone(frappe.cache.hget(f"bible_text:{self.free}", "books"))
		frappe.get_doc("Bible Translation", self.free).save(ignore_permissions=True)
		self.assertIsNone(frappe.cache.hget(f"bible_text:{self.free}", "books"))

	def test_the_church_default_is_read_first_and_answers_for_no_translation(self):
		with patch.object(scripture, "get_default_translation", return_value=self.imported):
			self.assertEqual(scripture.get_readable_translations()[0].name, self.imported)
			self.assertEqual(scripture.get_chapter("JHN", 4, None)[0]["number"], 1)
		with patch.object(scripture, "get_default_translation", return_value=None):
			with self.assertRaisesRegex(frappe.ValidationError, "Default Bible Translation"):
				scripture.get_books()

	def test_a_named_church_answers_with_its_own_default(self):
		root = ensure_root_church()
		frappe.db.set_value("Church", root, "default_bible_translation", self.free)
		self.assertEqual(scripture.get_default_translation(root), self.free)

	def seeded_translation(self, abbreviation):
		"""A free translation inserted the way after_install seeds one: no text yet, no job queued."""
		doc = frappe.get_doc(
			{
				"doctype": "Bible Translation",
				"abbreviation": abbreviation,
				"translation": f"{abbreviation} Test Version",
				"source": scripture.FREE_USE_BIBLE_API,
				"source_id": "_TEST",
			}
		)
		doc.flags.skip_download = True
		doc.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Bible Translation", doc.name, force=True, ignore_permissions=True)
		self.addCleanup(scripture.clear_cache, doc.name)
		return doc

	def test_a_seeded_translation_waits_with_no_text_until_someone_reads_it(self):
		doc = self.seeded_translation("_TLZ")
		self.assertEqual(doc.status, "No Text")

		content = [{"type": "verse", "number": 16, "text": "For God so loved the world."}]
		data = free_use_bible([("JHN", "John", 3, content)])
		with patch.object(scripture, "download_free_use_bible", return_value=data) as download:
			self.assertTrue(scripture.is_readable(doc.name))
		download.assert_called_once_with("_TEST")
		self.addCleanup(frappe.get_doc("Bible Translation", doc.name).remove_text_file)

		self.assertEqual(frappe.db.get_value("Bible Translation", doc.name, "status"), "Ready")
		self.assertEqual(scripture.get_chapter("JHN", 3, doc.name), content)

	def test_listing_translations_does_not_download_an_unread_one(self):
		doc = self.seeded_translation("_TLL")
		with patch.object(scripture, "download_free_use_bible") as download:
			names = [translation.name for translation in scripture.get_readable_translations()]
		download.assert_not_called()
		self.assertIn(doc.name, names)


def free_use_bible(books):
	"""A Free Use Bible API complete.simple.json holding (id, name, chapter, content) chapters."""
	return {
		"translation": {"id": "_TEST"},
		"books": [
			{"id": book, "name": name, "chapters": [{"chapter": {"number": number, "content": content}}]}
			for book, name, number, content in books
		],
	}
