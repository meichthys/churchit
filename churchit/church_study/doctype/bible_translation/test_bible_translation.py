# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from churchit import scripture
from churchit.tests.helpers import ensure_user
from churchit.tests.test_scripture import free_use_bible

CHAPTER = [{"type": "verse", "number": 1, "text": "In the beginning."}]


class TestBibleTranslation(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def free_translation(self, abbreviation="_TFU"):
		frappe.delete_doc("Bible Translation", abbreviation, force=True, ignore_missing=True)
		with patch("frappe.enqueue_doc") as enqueue:
			doc = frappe.get_doc(
				{
					"doctype": "Bible Translation",
					"abbreviation": abbreviation,
					"translation": "_Test Free Version",
					"source": scripture.FREE_USE_BIBLE_API,
					"source_id": "_TEST",
				}
			).insert(ignore_permissions=True)
		self.addCleanup(scripture.clear_cache, abbreviation)
		# A download writes a real file, which the rollback would leave on disk.
		self.addCleanup(doc.remove_text_file)
		return doc, enqueue

	def private_file(self, name, content, is_private=1):
		file = frappe.get_doc(
			{"doctype": "File", "file_name": name, "content": content, "is_private": is_private}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "File", file.name, force=True, ignore_permissions=True)
		return file.file_url

	def test_a_free_translation_queues_its_download_on_insert(self):
		doc, enqueue = self.free_translation()
		self.assertEqual(doc.status, "Downloading")
		self.assertEqual(enqueue.call_args.args[2], "download_text")
		self.assertTrue(enqueue.call_args.kwargs["enqueue_after_commit"])

	def test_flags_skip_download_seeds_it_with_no_text_and_queues_nothing(self):
		frappe.delete_doc("Bible Translation", "_TSK", force=True, ignore_missing=True)
		self.addCleanup(scripture.clear_cache, "_TSK")
		doc = frappe.get_doc(
			{
				"doctype": "Bible Translation",
				"abbreviation": "_TSK",
				"translation": "_Test Skipped Version",
				"source": scripture.FREE_USE_BIBLE_API,
				"source_id": "_TEST",
			}
		)
		doc.flags.skip_download = True
		with patch("frappe.enqueue_doc") as enqueue:
			doc.insert(ignore_permissions=True)
		self.assertEqual(doc.status, "No Text")
		enqueue.assert_not_called()

	def test_a_download_attaches_a_private_file_and_fills_in_the_details(self):
		doc, _enqueue = self.free_translation()
		data = free_use_bible([("GEN", "Genesis", 1, CHAPTER)])
		data["translation"].update(
			languageEnglishName="English", textDirection="rtl", licenseUrl="https://example.com/license"
		)
		with patch.object(scripture, "download_free_use_bible", return_value=data):
			doc.download_text()

		doc.reload()
		self.assertEqual((doc.status, doc.verse_count, doc.language), ("Ready", 1, "English"))
		self.assertEqual((doc.text_direction, doc.license_url), ("rtl", "https://example.com/license"))
		self.assertTrue(frappe.db.get_value("File", {"file_url": doc.text_file}, "is_private"))
		self.assertEqual(scripture.get_chapter("GEN", 1, doc.name), CHAPTER)

	def test_downloading_again_replaces_the_file(self):
		doc, _enqueue = self.free_translation()
		for text in ("First.", "Second."):
			chapter = [{"type": "verse", "number": 1, "text": text}]
			with patch.object(
				scripture,
				"download_free_use_bible",
				return_value=free_use_bible([("GEN", "Genesis", 1, chapter)]),
			):
				doc.download_text()
		files = frappe.get_all(
			"File", filters={"attached_to_name": doc.name, "attached_to_field": "text_file"}
		)
		self.assertEqual(len(files), 1)
		self.assertEqual(scripture.get_passage_text("Genesis 1:1", doc.name), "1 Second.")

	def test_a_failed_download_is_marked_and_logged(self):
		doc, _enqueue = self.free_translation()
		with patch.object(scripture, "download_free_use_bible", side_effect=requests.ConnectionError):
			doc.download_text()
		self.assertEqual(frappe.db.get_value("Bible Translation", doc.name, "status"), "Failed")
		self.assertTrue(frappe.db.exists("Error Log", {"reference_name": doc.name}))

	def test_a_queued_download_leaves_a_translation_switched_to_import_alone(self):
		doc, _enqueue = self.free_translation()
		frappe.db.set_value("Bible Translation", doc.name, "source", "User Import")
		with patch.object(scripture, "download_free_use_bible") as download:
			frappe.get_doc("Bible Translation", doc.name).download_text()
		download.assert_not_called()

	def test_download_again_needs_write_permission_and_a_free_translation(self):
		doc, _enqueue = self.free_translation()
		frappe.set_user(ensure_user("_test_translation_reader@example.com", "_Test Reader"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Bible Translation", doc.name).download_again()
		frappe.set_user("Administrator")
		frappe.db.set_value("Bible Translation", doc.name, "source", "User Import")
		with self.assertRaisesRegex(frappe.ValidationError, "Free Use Bible API"):
			frappe.get_doc("Bible Translation", doc.name).download_again()

	def test_an_import_is_read_on_save(self):
		url = self.private_file(
			"_test_import.csv", "book,chapter,verse,text\nJHN,3,16,For God\nJHN,3,17,For God did not\n"
		)
		doc = self.imported_translation(url)
		self.assertEqual((doc.status, doc.verse_count), ("Ready", 2))

	def test_an_import_needs_a_private_file_holding_verses(self):
		public = self.private_file("_test_public.csv", "book,chapter,verse,text\nJHN,3,16,x\n", is_private=0)
		with self.assertRaisesRegex(frappe.ValidationError, "private"):
			self.imported_translation(public)
		empty = self.private_file("_test_empty.csv", "book,chapter,verse,text\n")
		with self.assertRaisesRegex(frappe.ValidationError, "no verses"):
			self.imported_translation(empty)

	def test_an_import_without_its_file_waits_for_one(self):
		self.assertEqual(self.imported_translation(None).status, "No Text")

	def test_a_free_translation_needs_its_id(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Free Use Bible API ID"):
			frappe.get_doc(
				{
					"doctype": "Bible Translation",
					"abbreviation": "_TNI",
					"translation": "_Test No Id Version",
					"source": scripture.FREE_USE_BIBLE_API,
				}
			).insert(ignore_permissions=True)

	def imported_translation(self, text_file):
		frappe.delete_doc("Bible Translation", "_TUI", force=True, ignore_missing=True)
		self.addCleanup(scripture.clear_cache, "_TUI")
		return frappe.get_doc(
			{
				"doctype": "Bible Translation",
				"abbreviation": "_TUI",
				"translation": "_Test Imported Version",
				"source": "User Import",
				"text_file": text_file,
			}
		).insert(ignore_permissions=True)
