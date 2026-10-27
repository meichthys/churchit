# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils.html_utils import sanitize_html

from churchit.church_scope import is_multi_church
from churchit.church_study.doctype.sermon_handout.sermon_handout import fillable_content
from churchit.church_study.media import get_embed_url

no_cache = 1
# Only /sermon/<name> shows a sermon; the bare route is a 404.
sitemap = 0


def get_context(context):
	"""One published sermon, for anyone with its link, whichever church page they come from."""
	# A query string also fills form_dict, so /sermon?name=<name> must not open it.
	if not frappe.local.path.startswith("sermon/"):
		raise frappe.PageDoesNotExistError
	sermon = get_published_sermon(frappe.form_dict.get("name"))
	context.no_cache = 1
	context.title = sermon.title
	context.sermon = sermon
	context.embed_url = get_embed_url(sermon.media_url)
	context.preacher = sermon.prepared_by and frappe.db.get_value("Person", sermon.prepared_by, "full_name")
	context.series = sermon.series and frappe.db.get_value(
		"Sermon Series", {"name": sermon.series, "publish": 1}, ["series_name", "image"], as_dict=True
	)
	content = sermon.handout and frappe.db.get_value("Sermon Handout", sermon.handout, "content")
	# The handout replaces the notes: Make Handout copies them, and their [bracketed] words are its answer key.
	if content:
		context.handout = fillable_content(sanitize_html(content, always_sanitize=True))
	else:
		context.notes = sanitize_html(sermon.get("notes") or "", always_sanitize=True)


def get_published_sermon(name: str | None) -> frappe._dict:
	"""The published sermon *name*; a church that is not published hides its sermons."""
	sermon = name and frappe.db.get_value(
		"Sermon",
		{"name": name, "publish": 1},
		[
			"name",
			"title",
			"church",
			"sermon_date",
			"scripture",
			"prepared_by",
			"series",
			"audio_recording",
			"media_url",
			"notes",
			"handout",
		],
		as_dict=True,
	)
	if not sermon:
		raise frappe.PageDoesNotExistError
	if is_multi_church() and sermon.church and not frappe.db.get_value("Church", sermon.church, "publish"):
		raise frappe.PageDoesNotExistError
	return sermon
