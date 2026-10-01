# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint

from churchit.scripture import get_books, get_chapter, get_readable_translations

# What a visitor may read depends on who they are, so a rendered page is never shared.
no_cache = 1


def get_context(context):
	context.title = _("Bible")
	context.church = frappe.form_dict.get("church")
	context.translations = get_readable_translations()
	if not context.translations:
		return
	requested = frappe.form_dict.get("translation")
	context.translation = next(
		(translation for translation in context.translations if translation.name == requested),
		context.translations[0],
	)
	context.books = get_books(context.translation.name)
	requested = (frappe.form_dict.get("book") or "").upper()
	context.book = next((book for book in context.books if book["id"] == requested), context.books[0])
	context.chapter = min(max(cint(frappe.form_dict.get("chapter")), 1), context.book["chapters"])
	context.content = get_chapter(context.book["id"], context.chapter, context.translation.name)
	context.previous_url, context.next_url = (
		get_chapter_url(context.translation.name, *neighbour, context.church) if neighbour else None
		for neighbour in get_neighbours(context.books, context.book["id"], context.chapter)
	)


def get_neighbours(books, book, chapter):
	"""The (book, chapter) before and after this one, running on from one book into the next."""
	chapters = [(entry["id"], number) for entry in books for number in range(1, entry["chapters"] + 1)]
	position = chapters.index((book, chapter))
	previous = chapters[position - 1] if position else None
	following = chapters[position + 1] if position + 1 < len(chapters) else None
	return previous, following


def get_chapter_url(translation, book, chapter, church=None):
	"""A chapter's address, keeping the visitor's chosen church (see site_church.js)."""
	params = {"translation": translation, "book": book, "chapter": chapter}
	if church:
		params["church"] = church
	return f"/bible?{urlencode(params)}"
