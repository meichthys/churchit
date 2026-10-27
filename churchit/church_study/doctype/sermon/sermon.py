# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils import getdate

from churchit.scripture import format_reference
from churchit.utils import validate_https_url


class Sermon(Document):
	def validate(self):
		if not self.sermon_date:
			self.sermon_date = min(
				(getdate(row.date) for row in self.presentation_history if row.date), default=None
			)
		self.scripture = format_reference(self.scripture)
		if self.media_url and self.has_value_changed("media_url"):
			self.media_url = validate_https_url(self.media_url, "Video Link")

		for slide in self.slides:
			slide.scripture = format_reference(slide.scripture)
			if not (slide.scripture or (slide.slide_type and slide.slide)):
				frappe.throw(_("Slide {0} needs a record to show or a Scripture passage.").format(slide.idx))

	def before_save(self):
		if not self.is_new() and self.has_value_changed("title") and self.title != self.name:
			rename_doc(self.doctype, self.name, self.title, merge=False)
			self.name = self.title

	def on_update(self):
		"""Keep every recording public exactly while the sermon is published, so the podcast can play it.

		A file that moves between /private/files and /files gets a new URL. Frappe writes it into
		the field the file was uploaded to, which for a presentation row is the sermon's own
		`audio_recording`, and stamps a new `modified`. So after any move the sermon's value is
		written again with this save's `modified`, which keeps the open form saveable.
		"""
		rows = [self, *self.presentation_history]
		moved = {}
		for file_url in {row.audio_recording for row in rows if row.audio_recording}:
			new_url = self.set_recording_privacy(file_url)
			if new_url != file_url:
				moved[file_url] = new_url
		if not moved:
			return

		# Inside a save, db_set writes the doc's own `modified` back instead of a new one.
		self.db_set("audio_recording", moved.get(self.audio_recording, self.audio_recording))
		for row in self.presentation_history:
			if row.audio_recording in moved:
				row.db_set("audio_recording", moved[row.audio_recording], update_modified=False)

	def set_recording_privacy(self, file_url: str) -> str:
		"""Make this sermon's file at *file_url* private unless the sermon is published; return its URL."""
		name = frappe.db.get_value(
			"File",
			{"file_url": file_url, "attached_to_doctype": "Sermon", "attached_to_name": self.name},
			"name",
		)
		if not name:
			return file_url
		file = frappe.get_doc("File", name)
		is_private = int(not self.publish)
		if file.is_private != is_private:
			file.is_private = is_private
			file.save(ignore_permissions=True)
		return file.file_url
