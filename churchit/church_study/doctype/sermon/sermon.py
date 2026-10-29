# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.utils import getdate
from frappe.website.utils import clear_cache as clear_website_cache

from churchit.church_scope import refuse_another_churches_record
from churchit.scripture import format_reference
from churchit.utils import validate_https_url
from churchit.www.sermon import get_published_sermon


class Sermon(Document):
	def validate(self):
		if not self.sermon_date:
			self.sermon_date = min(
				(getdate(row.date) for row in self.presentation_history if row.date), default=None
			)
		self.scripture = format_reference(self.scripture)
		if self.media_url and self.has_value_changed("media_url"):
			self.media_url = validate_https_url(self.media_url, "Video Link")
		# The sermon page shows the handout to anyone, so it must be this church's or a shared one.
		if any(self.has_value_changed(field) for field in ("handout", "church", "is_shared")):
			refuse_another_churches_record(self, "Sermon Handout", self.handout)

		for slide in self.slides:
			slide.scripture = format_reference(slide.scripture)
			if not (slide.scripture or (slide.slide_type and slide.slide)):
				frappe.throw(_("Slide {0} needs a record to show or a Scripture passage.").format(slide.idx))

	def before_save(self):
		if not self.is_new() and self.has_value_changed("title") and self.title != self.name:
			rename_doc(self.doctype, self.name, self.title, merge=False)
			self.name = self.title

	def after_rename(self, old: str, new: str, merge: bool = False):
		"""Send the old /sermon link to the new one in one hop, while the public can open the sermon.

		Only the Website Settings redirect rows are written: a full save runs unrelated Website
		Settings checks and clears the whole site cache.
		"""
		old_source, new_source = (f"sermon/{re.escape(name)}" for name in (old, new))
		old_target, new_target = (f"/sermon/{quote(name)}" for name in (old, new))
		rows = {
			"parenttype": "Website Settings",
			"parent": "Website Settings",
			"parentfield": "route_redirects",
		}
		# The new name is a live page again, so a redirect away from it must go.
		frappe.db.delete("Website Route Redirect", {**rows, "source": new_source})

		# A redirect from a draft's old links would show its new title to a Guest.
		if self.is_public:
			frappe.db.set_value(
				"Website Route Redirect", {**rows, "target": old_target}, "target", new_target
			)
			frappe.get_doc(
				{
					"doctype": "Website Route Redirect",
					**rows,
					"idx": frappe.db.count("Website Route Redirect", rows) + 1,
					"source": old_source,
					"target": new_target,
					"redirect_http_status": 301,
					"forward_query_parameters": 1,
				}
			).db_insert()

		# Bumps `modified`, so a Website Settings form opened before the rename must reload to save.
		frappe.db.set_single_value("Website Settings", {})
		clear_website_cache()

	@property
	def is_public(self) -> bool:
		"""True when a Guest can open the sermon page, by the rule of `get_published_sermon`."""
		try:
			get_published_sermon(self.name)
		except frappe.PageDoesNotExistError:
			return False
		return True

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
