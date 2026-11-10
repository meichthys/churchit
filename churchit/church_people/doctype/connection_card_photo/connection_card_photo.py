# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, get_datetime, now_datetime

from churchit.ai.switch import has_flow

PHOTO = "Connection Card Photo"
CARD = "Connection Card"
WAITING = "Waiting"
READING = "Reading"
READY = "Ready to Check"
IMPORTED = "Imported"
FAILED = "Failed"
READ_AGAIN_STATUSES = (FAILED, READY)
# A photo that waits or reads this long lost its job or its run (a Data Import, a Flow restart).
STUCK_SECONDS = 60 * 60
PRIVATE_FILES = "/private/files/"


class ConnectionCardPhoto(Document):
	"""A photo of a paper connection card, the draft AI read from it (churchit.ai.card_capture) and the
	Connection Card that a person made from that draft."""

	def validate(self):
		if self.photo and not self.photo.startswith(PRIVATE_FILES):
			frappe.throw(_("Upload the card photo as a private file."))

	def onload(self):
		self.set_onload("is_readable_again", self.is_readable_again)

	def on_trash(self):
		if self.connection_card:
			frappe.db.set_value(CARD, self.connection_card, "card_photo", None, update_modified=False)
		self.forget_chats()

	@property
	def is_readable_again(self) -> bool:
		"""True when Read Again may queue the photo: it failed, its draft is ready to check, or it has
		waited or been reading for STUCK_SECONDS."""
		if self.status in READ_AGAIN_STATUSES:
			return True
		since = add_to_date(now_datetime(), seconds=-STUCK_SECONDS)
		return self.status in (WAITING, READING) and get_datetime(self.modified) < since

	def get_file(self) -> str | None:
		"""The private File of the photo, attached to this record, or None."""
		if not self.photo:
			return None
		filters = {
			"file_url": self.photo,
			"attached_to_doctype": self.doctype,
			"attached_to_name": self.name,
			"is_private": 1,
		}
		return frappe.db.get_value("File", filters, "name")

	def forget_chats(self) -> None:
		"""Delete the Flow chats that read this photo, with their runs."""
		if not has_flow():
			return
		runs = {"reference_doctype": self.doctype, "reference_name": self.name}
		for session in set(frappe.get_all("Flow Run", filters=runs, pluck="session")):
			frappe.delete_doc("Flow Session", session, ignore_permissions=True, delete_permanently=True)

	def check_can_import(self) -> None:
		"""Connection Card validate: refuse a new card from a photo that the user cannot change, or one
		that has no draft to import."""
		self.check_permission("write")
		if self.status != READY:
			frappe.throw(_("This card photo has no draft to import, or it has its connection card already."))

	def mark_imported(self, card: str) -> None:
		"""Connection Card after_insert: link the photo to its new card."""
		self.db_set({"connection_card": card, "status": IMPORTED}, notify=True)
