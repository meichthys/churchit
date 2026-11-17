# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint

from churchit.scripture import TRANSLATION, get_books, get_chapter, get_readable_translations

# What a visitor may read depends on who they are, so a rendered page is never shared.
no_cache = 1


def get_context(context):
	context.title = _("Bible")
	# The page is public; the portal menu is only for signed-in members.
	context.show_sidebar = frappe.session.user != "Guest"
	context.church = frappe.form_dict.get("church")
	context.translations = get_readable_translations()
	if not context.translations:
		return
	context.translation, context.books = open_translation(context, frappe.form_dict.get("translation"))
	if not context.translation:
		context.translations = []
		return
	requested = (frappe.form_dict.get("book") or "").upper()
	context.book = next((book for book in context.books if book["id"] == requested), context.books[0])
	context.chapter = min(max(cint(frappe.form_dict.get("chapter")), 1), context.book["chapters"])
	context.content = get_chapter(context.book["id"], context.chapter, context.translation.name)
	context.previous_url, context.next_url = (
		get_chapter_url(context.translation.name, *neighbour, context.church) if neighbour else None
		for neighbour in get_neighbours(context.books, context.book["id"], context.chapter)
	)


def open_translation(context, requested):
	"""The translation to read and its books: the one asked for, else the first that opens.

	One that cannot be read, such as a download that fails, gives way to a ready one with a notice.
	Only the first choice can start a download, so the page waits for one download at most.
	"""
	first = next((item for item in context.translations if item.name == requested), context.translations[0])
	ready = [item for item in context.translations if item.status == "Ready" and item is not first]
	wanted = requested if requested and frappe.db.exists(TRANSLATION, requested) else first.name
	for translation in (first, *ready):
		try:
			books = get_books(translation.name)
		except frappe.PermissionError:
			frappe.clear_messages()
			continue
		if translation.name != wanted:
			context.notice = _("{0} is not available now. {1} is shown instead.").format(
				wanted, translation.name
			)
		return translation, books
	return None, None


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
