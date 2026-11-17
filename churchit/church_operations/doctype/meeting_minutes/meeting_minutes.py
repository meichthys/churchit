# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname
from frappe.utils import getdate, today

from churchit.church_people.repeated_rows import refuse_repeated_people

MEETING_MINUTES = "Meeting Minutes"
PUBLISHED = "Published"
STAFF_ROLE = "Church Staff"
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".webm"}


class MeetingMinutes(Document):
	def autoname(self):
		"""MM-0001 and on. Frappe 17's Expression naming reads the MM of "MM-.####" as the month."""
		self.name = make_autoname(self.meta.autoname, doc=self)

	def validate(self):
		self.validate_audio_recording()
		refuse_repeated_people(self, "attendees", "person")
		self.validate_approval_date()
		if self.status in ("Approved", "Published") and not self.approved_on:
			self.approved_on = today()

	def validate_approval_date(self):
		"""Refuse an approval date before the meeting date, when this save sets either."""
		changed = (
			self.is_new() or self.has_value_changed("meeting_date") or self.has_value_changed("approved_on")
		)
		if (
			changed
			and self.meeting_date
			and self.approved_on
			and getdate(self.approved_on) < getdate(self.meeting_date)
		):
			frappe.throw(_("Approved On cannot be before the Meeting Date."))

	def validate_audio_recording(self):
		if not self.audio_recording:
			return
		extension = os.path.splitext(self.audio_recording.split("?")[0])[1].lower()
		if extension not in AUDIO_EXTENSIONS:
			frappe.throw(
				_("Audio Recording must be an audio file ({0}).").format(", ".join(sorted(AUDIO_EXTENSIONS))),
				title=_("Invalid Recording"),
			)


def has_minutes_permission(doc, ptype=None, user=None) -> bool:
	"""has_permission hook: a user who reads minutes only as Church Staff reads only Published ones.

	Frappe reads any falsy return as a refusal, so every other user gets True.
	"""
	return doc.status == PUBLISHED or not reads_only_published(user or frappe.session.user)


def minutes_query_conditions(user=None, doctype=None) -> str:
	"""permission_query_conditions hook: Church Staff list only Published minutes."""
	if not reads_only_published(user or frappe.session.user):
		return ""
	return f"`tabMeeting Minutes`.`status` = {frappe.db.escape(PUBLISHED)}"


def reads_only_published(user: str) -> bool:
	"""True when *user* reads minutes only through the Church Staff role."""
	readers = {
		perm.role for perm in frappe.get_meta(MEETING_MINUTES).permissions if perm.read and not perm.permlevel
	}
	return readers & set(frappe.get_roles(user)) == {STAFF_ROLE}
