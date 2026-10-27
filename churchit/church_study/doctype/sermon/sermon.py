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
		if self.audio_recording:
			file_doc = frappe.db.get_value(
				"File",
				{
					"file_url": self.audio_recording,
					"attached_to_doctype": "Sermon",
					"attached_to_name": self.name,
				},
				"name",
			)
			if file_doc:
				f = frappe.get_doc("File", file_doc)
				should_be_private = not self.publish
				if f.is_private != should_be_private:
					f.is_private = should_be_private
					f.save(ignore_permissions=True)
					if f.file_url != self.audio_recording:
						frappe.db.set_value("Sermon", self.name, "audio_recording", f.file_url)
