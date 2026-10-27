# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSermon(FrappeTestCase):
	def _sermon(self, title, **values):
		if frappe.db.exists("Sermon", {"title": title}):
			frappe.delete_doc("Sermon", frappe.db.get_value("Sermon", {"title": title}), force=True)
		return frappe.get_doc({"doctype": "Sermon", "title": title, **values}).insert(ignore_permissions=True)

	def _attach_audio(self, sermon, is_private):
		# A remote URL keeps Frappe from moving anything on disk when privacy flips.
		return frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{sermon.name}.mp3",
				"file_url": f"https://example.com/{frappe.scrub(sermon.name)}.mp3",
				"is_private": is_private,
				"attached_to_doctype": "Sermon",
				"attached_to_name": sermon.name,
				"attached_to_field": "audio_recording",
			}
		).insert(ignore_permissions=True)

	def test_renaming_title_renames_the_record(self):
		sermon = self._sermon("_Test Original Title")
		sermon.title = "_Test Renamed Title"
		sermon.save(ignore_permissions=True)

		self.assertEqual(sermon.name, "_Test Renamed Title")
		self.assertTrue(frappe.db.exists("Sermon", "_Test Renamed Title"))

	def test_publishing_makes_the_audio_file_public(self):
		sermon = self._sermon("_Test Audio Sermon")
		audio = self._attach_audio(sermon, is_private=1)
		sermon.audio_recording = audio.file_url
		sermon.publish = 1
		sermon.save(ignore_permissions=True)

		self.assertFalse(frappe.db.get_value("File", audio.name, "is_private"))

	def test_unpublishing_makes_the_audio_file_private(self):
		sermon = self._sermon("_Test Private Audio Sermon", publish=1)
		audio = self._attach_audio(sermon, is_private=0)
		sermon.audio_recording = audio.file_url
		sermon.save(ignore_permissions=True)
		self.assertFalse(frappe.db.get_value("File", audio.name, "is_private"))

		sermon.publish = 0
		sermon.save(ignore_permissions=True)
		self.assertTrue(frappe.db.get_value("File", audio.name, "is_private"))

	def test_a_blank_sermon_date_comes_from_the_first_presentation(self):
		history = [{"date": "2031-03-01"}, {"date": "2030-01-05"}]

		sermon = self._sermon("_Test Dated Sermon", presentation_history=history)
		self.assertEqual(str(sermon.sermon_date), "2030-01-05")

		sermon.sermon_date = "2029-12-25"
		sermon.save(ignore_permissions=True)
		self.assertEqual(str(sermon.sermon_date), "2029-12-25")

		self.assertIsNone(self._sermon("_Test Undated Sermon").sermon_date)

	def test_the_scripture_is_tidied_on_save(self):
		sermon = self._sermon("_Test Scripture Sermon", scripture="jn 3:16; ps 23")
		self.assertEqual(sermon.scripture, "John 3:16; Psalms 23")

	def test_the_video_link_must_be_one_https_link(self):
		for url in ("javascript:alert(1)", "http://x.org", "https://x.org/a b"):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				self._sermon("_Test Video Sermon", media_url=url)

		sermon = self._sermon("_Test Video Sermon", media_url=" https://lets.church/media/abc ")
		self.assertEqual(sermon.media_url, "https://lets.church/media/abc")

	def test_the_outline_prints_the_newest_presentation(self):
		sermon = self._sermon(
			"_Test Outlined Sermon",
			presentation_history=[
				{"date": "2031-03-01", "location": "_Test Newer Hall"},
				{"date": "2030-01-05", "location": "_Test Older Hall"},
			],
		)

		html = frappe.get_print("Sermon", sermon.name, print_format="Sermon Outline")

		self.assertIn(frappe.utils.formatdate("2031-03-01"), html)
		self.assertIn("_Test Newer Hall", html)
		self.assertNotIn("_Test Older Hall", html)
