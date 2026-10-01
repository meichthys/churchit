# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document

from churchit import scripture


class BibleTranslation(Document):
	def validate(self):
		if self.is_free_use:
			if not self.source_id:
				frappe.throw(_("Enter the translation's Free Use Bible API ID, such as BSB."))
			changed = self.has_value_changed("source") or self.has_value_changed("source_id")
			# flags.skip_download: seeded without fetching its text yet, by after_install or the
			# migration patch; churchit.scripture.is_readable downloads it the first time it is read.
			if changed and not self.flags.skip_download:
				self.status = "Downloading"
				self.flags.queue_download = True
		elif self.has_value_changed("source") or self.has_value_changed("text_file"):
			self.read_text_file()

	def on_update(self):
		scripture.clear_cache(self.name)
		if self.flags.queue_download:
			self.queue_download()

	def on_trash(self):
		scripture.clear_cache(self.name)

	def after_rename(self, old, new, merge=False):
		scripture.clear_cache(old)

	@property
	def is_free_use(self):
		return self.source == scripture.FREE_USE_BIBLE_API

	def read_text_file(self):
		"""Parse an imported file on save, so a bad file fails here rather than in the reader."""
		self.status, self.verse_count = "No Text", 0
		if not self.text_file:
			return
		if not frappe.db.get_value("File", {"file_url": self.text_file}, "is_private"):
			frappe.throw(_("Attach the text as a private file, so the website does not publish it."))
		self.verse_count = scripture.count_verses(scripture.load_text(self.text_file))
		if not self.verse_count:
			frappe.throw(_("{0} holds no verses.").format(self.text_file))
		self.status = "Ready"

	@frappe.whitelist()
	def download_again(self):
		self.check_permission("write")
		if not self.is_free_use:
			frappe.throw(_("Only a Free Use Bible API translation can be downloaded."))
		self.db_set("status", "Downloading")
		self.queue_download()

	def queue_download(self):
		frappe.enqueue_doc(
			self.doctype, self.name, "download_text", queue="long", timeout=900, enqueue_after_commit=True
		)

	def download_text(self):
		"""Background job: fetch the whole translation and attach it as a private file."""
		if not self.is_free_use:
			return
		try:
			data = scripture.download_free_use_bible(self.source_id)
			verse_count = scripture.count_verses(scripture.from_free_use_json(data))
		except (requests.RequestException, KeyError, TypeError, ValueError):
			self.log_error(_("Could not download {0} from the Free Use Bible API").format(self.name))
			self.db_set("status", "Failed")
			return
		self.attach_text(data, verse_count)

	def attach_text(self, data, verse_count):
		"""Replace the text file with a Free Use Bible API download and fill in what it says about itself."""
		self.remove_text_file()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{self.name}.json",
				"content": json.dumps(data, ensure_ascii=False),
				"is_private": 1,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"attached_to_field": "text_file",
			}
		).insert(ignore_permissions=True)
		details = data.get("translation") or {}
		self.db_set(
			{
				"text_file": file.file_url,
				"status": "Ready",
				"verse_count": verse_count,
				"language": self.language or details.get("languageEnglishName"),
				"text_direction": details.get("textDirection") or "ltr",
				"website": self.website or details.get("website"),
				"license_url": self.license_url or details.get("licenseUrl"),
			}
		)
		scripture.clear_cache(self.name)

	def remove_text_file(self):
		for file in frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
				"attached_to_field": "text_file",
			},
			pluck="name",
		):
			frappe.delete_doc("File", file, ignore_permissions=True)
