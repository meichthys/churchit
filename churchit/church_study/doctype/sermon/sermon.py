# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc


class Sermon(Document):
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
