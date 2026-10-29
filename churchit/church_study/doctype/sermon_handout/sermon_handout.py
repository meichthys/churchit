# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import itertools
import re

import frappe
from frappe import _
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


def fillable_content(content: str | None) -> str:
	"""*content* for a listener's screen, with a text input for every [bracketed phrase].

	The bracketed words are the answer key, so they never reach the page.
	"""
	numbers = itertools.count(1)
	return BLANK.sub(lambda match: input_for(match, next(numbers)), content or "")


def input_for(match, number):
	size = max(4, len(match.group(1)))
	label = _("Blank {0}").format(number)
	return (
		f'<input type="text" class="handout-blank" data-blank="{number}" size="{size}" '
		f'aria-label="{label}" autocomplete="off">'
	)


@frappe.whitelist(methods=["POST"])
def make_handout(sermon: str):
	"""Create a handout from the sermon's notes, link it from the sermon, and return its name."""
	sermon = frappe.get_doc("Sermon", sermon)
	sermon.check_permission("write")
	handout = frappe.get_doc(
		{"doctype": "Sermon Handout", "title": sermon.title, "content": sermon.notes}
	).insert()
	sermon.db_set("handout", handout.name)
	return handout.name
