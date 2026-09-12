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
