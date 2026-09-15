# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re

import frappe
from frappe.model.document import Document

BLANK = re.compile(r"\[([^\[\]]+)\]")


class SermonHandout(Document):
	@property
	def rendered_content(self):
		"""The content with every [bracketed phrase] replaced by a ruled blank sized to it."""
		return BLANK.sub(blank_for, self.content or "")


def blank_for(match):
	width = max(4, round(len(match.group(1)) * 0.8))
	return (
		f'<span class="blank" style="display:inline-block;min-width:{width}em;'
		'border-bottom:1px solid #222">&nbsp;</span>'
	)


@frappe.whitelist()
def make_handout(sermon):
	"""Create a handout from the sermon's notes, link it from the sermon, and return its name."""
	sermon = frappe.get_doc("Sermon", sermon)
	sermon.check_permission("write")
	handout = frappe.get_doc(
		{"doctype": "Sermon Handout", "title": sermon.title, "content": sermon.notes}
	).insert()
	sermon.db_set("handout", handout.name)
	return handout.name
