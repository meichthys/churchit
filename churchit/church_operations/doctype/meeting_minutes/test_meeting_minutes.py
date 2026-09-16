# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMeetingMinutes(FrappeTestCase):
	def minutes(self, audio_recording=None):
		return frappe.get_doc(
			{
				"doctype": "Meeting Minutes",
				"title": "_Test Meeting",
				"meeting_date": "2026-01-01",
				"audio_recording": audio_recording,
			}
		)

	def test_audio_recording_accepts_audio_files(self):
		doc = self.minutes("/private/files/board-meeting.MP3").insert()
		self.addCleanup(doc.delete)
		self.assertEqual(doc.audio_recording, "/private/files/board-meeting.MP3")

	def test_audio_recording_rejects_non_audio_files(self):
		with self.assertRaises(frappe.ValidationError):
			self.minutes("/private/files/board-meeting.pdf").insert()

	def test_audio_recording_is_optional(self):
		doc = self.minutes().insert()
		self.addCleanup(doc.delete)
		self.assertFalse(doc.audio_recording)
