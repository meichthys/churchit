# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import escape_html

from churchit.church_ministries.songs import chordpro


class Song(Document):
	def validate(self):
		self.refuse_arrangements_with_one_name()

	def refuse_arrangements_with_one_name(self):
		names = set()
		for row in self.arrangements:
			name = (row.arrangement_name or "").strip().casefold()
			if not name:
				continue  # the mandatory check reports it
			if name in names:
				frappe.throw(
					_("Row {0}: this song already has an arrangement named {1}.").format(
						row.idx, frappe.bold(row.arrangement_name)
					),
					frappe.UniqueValidationError,
				)
			names.add(name)

	def get_arrangement_with_chart(self, arrangement: str) -> Document:
		"""The arrangement named *arrangement*, refused when it is missing or has no ChordPro chart."""
		row = next((row for row in self.arrangements if row.arrangement_name == arrangement), None)
		if not row:
			frappe.throw(
				_("{0} has no arrangement named {1}.").format(self.title, frappe.bold(arrangement)),
				frappe.DoesNotExistError,
			)
		if not row.chordpro:
			frappe.throw(_("The arrangement {0} has no ChordPro chart.").format(frappe.bold(arrangement)))
		return row


@frappe.whitelist(methods=["GET"])
def render_chord_chart(song: str, arrangement: str, key: str | None = None) -> str:
	"""The arrangement's chord chart as HTML, transposed to *key* when it is given."""
	doc = frappe.get_doc("Song", song)
	doc.check_permission("read")
	row = doc.get_arrangement_with_chart(arrangement)
	written_in = row.song_key or doc.default_key
	if not key or key == written_in:
		return chordpro.to_html(row.chordpro)

	if key not in frappe.get_meta("Song Arrangement").get_options("song_key").split("\n"):
		frappe.throw(_("{0} is not a key.").format(escape_html(key)))
	if not written_in:
		frappe.throw(_("Set the key of {0} before you choose another key.").format(frappe.bold(arrangement)))
	if key.endswith("m") != written_in.endswith("m"):
		message = (
			_("Choose a minor key for {0}.") if written_in.endswith("m") else _("Choose a major key for {0}.")
		)
		frappe.throw(message.format(frappe.bold(arrangement)))
	return chordpro.to_html(chordpro.transpose(row.chordpro, written_in, key))


@frappe.whitelist(methods=["POST"])
def make_slides(song: str, arrangement: str) -> int:
	"""Replace the song's slides with one slide for each section of the arrangement's lyrics."""
	doc = frappe.get_doc("Song", song)
	doc.check_permission("write")
	sections = chordpro.lyrics(doc.get_arrangement_with_chart(arrangement).chordpro)
	if not sections:
		frappe.throw(_("The chart of {0} has no lyrics.").format(frappe.bold(arrangement)))

	doc.set(
		"slides",
		[
			{"content": "<p>{}</p>".format("<br>".join(escape_html(line) for line in section["lines"]))}
			for section in sections
		],
	)
	doc.save()
	return len(doc.slides)
