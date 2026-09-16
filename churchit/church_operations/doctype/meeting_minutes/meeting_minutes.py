# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import os

import frappe
from frappe import _
from frappe.model.document import Document

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".webm"}


class MeetingMinutes(Document):
	def validate(self):
		self.validate_audio_recording()

	def validate_audio_recording(self):
		if not self.audio_recording:
			return
		extension = os.path.splitext(self.audio_recording.split("?")[0])[1].lower()
		if extension not in AUDIO_EXTENSIONS:
			frappe.throw(
				_("Audio Recording must be an audio file ({0}).").format(", ".join(sorted(AUDIO_EXTENSIONS))),
				title=_("Invalid Recording"),
			)
