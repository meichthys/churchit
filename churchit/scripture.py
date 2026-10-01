# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Bible references, and the text of each Bible Translation.

A reference is plain text such as "Psalms 23; Romans 8:28-30", read with pythonbible, so no record
stands for a verse or a passage. A translation keeps its whole text in one private attached file,
which is parsed once and cached in Redis a chapter at a time.
"""

import csv
import io
import json

import frappe
import pythonbible
import requests
from frappe import _

from churchit.church_foundations.doctype.church.church import get_church, inherited_value

TRANSLATION = "Bible Translation"
FREE_USE_BIBLE_API = "Free Use Bible API"
FREE_USE_BIBLE_API_URL = "https://bible.helloao.org/api"
CSV_COLUMNS = ("book", "chapter", "verse", "text")

# USFM book ids in pythonbible's Book order, so Book(1) is GEN and Book(66) is REV.
USFM_BOOKS = (
	"GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB "
	"PSA PRO ECC SNG ISA JER LAM EZK DAN HOS JOL AMO OBA JON MIC NAM HAB ZEP "
	"HAG ZEC MAL MAT MRK LUK JHN ACT ROM 1CO 2CO GAL EPH PHP COL 1TH 2TH 1TI "
	"2TI TIT PHM HEB JAS 1PE 2PE 1JN 2JN 3JN JUD REV"
).split()


# References --------------------------------------------------------------------------------------


def parse_reference(text: str) -> list:
	"""The passages a reference names, as pythonbible NormalizedReferences."""
	references = pythonbible.get_references(text or "")
	if not references:
		frappe.throw(_("Could not read the Bible reference {0}.").format(frappe.bold(text)))
	for reference in references:
		if max(reference.book.value, (reference.end_book or reference.book).value) > len(USFM_BOOKS):
			frappe.throw(
				_("{0} is outside the 66 books of the Bible, which is not supported yet.").format(
					frappe.bold(reference.book.title)
				)
			)
	return references


def format_reference(text: str | None) -> str | None:
	"""Tidy a typed reference for storage, keeping the order and the chapter form typed:
	"jn 3:16; ps 23" becomes "John 3:16; Psalms 23", not reordered or expanded into verses."""
	if not text:
		return text
	return "; ".join(_format_one_reference(reference) for reference in parse_reference(text))


def _format_one_reference(reference) -> str:
	"""One passage as read, not as pythonbible's full-book formatter would expand it.

	pythonbible's own formatter writes out every verse of a whole chapter or book, so "Psalm 23"
	comes back "Psalms 23:1-6". Whichever of book, chapter or verse the user left out is left out
	here too; only a verse that was actually typed is shown.
	"""
	if reference.start_chapter is None:
		return _format_books(reference)
	if reference.start_verse is None:
		return _format_chapters(reference)
	return pythonbible.format_single_reference(reference)


def _format_books(reference) -> str:
	"""A reference naming no chapter at all: a whole book, or a span of whole books."""
	if reference.end_book and reference.end_book != reference.book:
		return f"{reference.book.title} - {reference.end_book.title}"
	return reference.book.title


def _format_chapters(reference) -> str:
	"""A reference naming chapters but no verse: a whole chapter, or a span of whole chapters."""
	start = _chapter_label(reference.book, reference.start_chapter)
	if reference.end_book and reference.end_book != reference.book:
		return f"{start} - {_chapter_label(reference.end_book, reference.end_chapter)}"
	if reference.end_chapter and reference.end_chapter != reference.start_chapter:
		return f"{start}-{reference.end_chapter}"
	return start


def _chapter_label(book, chapter: int) -> str:
	"""A book's chapter, or just the book when it only has the one (Jude 1 is just Jude)."""
	return book.title if pythonbible.get_number_of_chapters(book) == 1 else f"{book.title} {chapter}"


def get_verses_by_chapter(reference: str) -> dict[tuple[str, int], list[int]]:
	"""The verse numbers a reference covers, keyed by (USFM book id, chapter), in reading order."""
	chapters = {}
	for verse_id in pythonbible.convert_references_to_verse_ids(parse_reference(reference)):
		book, chapter, verse = pythonbible.get_book_chapter_verse(verse_id)
		chapters.setdefault((USFM_BOOKS[book.value - 1], chapter), []).append(verse)
	return chapters


# Reading a translation ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_books(translation: str | None = None) -> list[dict]:
	"""The books a translation holds, as [{"id": "GEN", "name": "Genesis", "chapters": 50}, …]."""
	return get_text(translation, "books")


@frappe.whitelist(allow_guest=True)
def get_chapter(book: str, chapter: int, translation: str | None = None) -> list[dict]:
	"""One chapter as Free Use Bible API content: heading, hebrew_subtitle, line_break and verse items."""
	return get_text(translation, f"{book.upper()}.{int(chapter)}") or []


@frappe.whitelist(allow_guest=True)
def get_passage(reference: str, translation: str | None = None) -> list[dict]:
	"""The verses of a reference, one entry per chapter it touches."""
	passage = []
	for (book, chapter), numbers in get_verses_by_chapter(reference).items():
		text = {
			item["number"]: item["text"]
			for item in get_chapter(book, chapter, translation)
			if item["type"] == "verse"
		}
		verses = [{"number": number, "text": text[number]} for number in numbers if number in text]
		passage.append({"book": book, "chapter": chapter, "verses": verses})
	return passage


def get_passage_text(reference: str, translation: str | None = None) -> str:
	"""A reference's verses as one line of numbered text, for print formats, web pages and memorizing."""
	return " ".join(
		f"{verse['number']} {' '.join(verse['text'].split())}"
		for section in get_passage(reference, translation)
		for verse in section["verses"]
	)


def get_default_translation(church: str | None = None) -> str | None:
	"""A church's default translation, inherited from the churches above it.

	Without a church, the church the request is about: the signed-in member's, or the website's.
	"""
	church = church or getattr(get_church(), "name", None)
	return inherited_value(church, "default_bible_translation") if church else None


@frappe.whitelist(allow_guest=True)
def get_readable_translations() -> list[dict]:
	"""Translations a reader may open: the church's default first, then by title.

	A Free Use Bible API translation is always offered, downloading its text the first time
	someone opens it if that has not happened yet (see is_readable). A User Import is offered
	once its text is ready, and only to a reader with permission on it.
	"""
	default = get_default_translation()
	translations = frappe.get_all(
		TRANSLATION,
		fields=["name", "translation", "text_direction", "source", "status"],
		order_by="translation asc",
	)
	selectable = [
		translation
		for translation in translations
		if translation.source == FREE_USE_BIBLE_API
		or (translation.status == "Ready" and frappe.has_permission(TRANSLATION, "read", translation.name))
	]
	return sorted(selectable, key=lambda translation: translation.name != default)


def is_readable(translation: str | None) -> bool:
	"""Whether a translation has text the session user may read right now.

	A Free Use Bible API translation seeded without its text downloads it the first time anyone
	asks for it, so installing the app does not fetch every translation's text up front. A
	church's own import may be under copyright, so only Free Use Bible API texts reach guests.
	"""
	if not translation:
		return False
	source, status = frappe.get_cached_value(TRANSLATION, translation, ["source", "status"]) or (None, None)
	if source == FREE_USE_BIBLE_API and status == "No Text":
		download_now(translation)
		source, status = frappe.db.get_value(TRANSLATION, translation, ["source", "status"])
	if status != "Ready":
		return False
	return source == FREE_USE_BIBLE_API or frappe.has_permission(TRANSLATION, "read", translation)


def download_now(translation: str):
	"""Download a Free Use Bible API translation immediately, rather than queuing a background job.

	Used the moment someone actually reads a translation seeded without its text, so the one-time
	download cost is paid by whoever opens it rather than by every site at install.
	"""
	frappe.db.set_value(TRANSLATION, translation, "status", "Downloading", update_modified=False)
	frappe.get_doc(TRANSLATION, translation).download_text()
	frappe.clear_document_cache(TRANSLATION, translation)


def get_text(translation: str | None, key: str):
	"""One cached piece of a translation's text: its "books", or a chapter such as "JHN.3"."""
	translation = translation or get_default_translation()
	if not translation:
		frappe.throw(_("Choose a Default Bible Translation on the Church form."))
	if not is_readable(translation):
		frappe.throw(_("The text of {0} is not available.").format(translation), frappe.PermissionError)
	cache_key = f"bible_text:{translation}"
	if frappe.cache.hget(cache_key, "books") is None:
		load_into_cache(translation, cache_key)
	return frappe.cache.hget(cache_key, key)


def load_into_cache(translation: str, cache_key: str):
	"""Cache every chapter, then the book list, whose presence marks the text as loaded."""
	books = load_text(frappe.db.get_value(TRANSLATION, translation, "text_file"))
	for book_id, book in books.items():
		for number, content in book["chapters"].items():
			frappe.cache.hset(cache_key, f"{book_id}.{number}", content)
	listing = [
		{"id": book_id, "name": book["name"], "chapters": len(book["chapters"])}
		for book_id, book in books.items()
	]
	frappe.cache.hset(cache_key, "books", listing)


def clear_cache(translation: str):
	frappe.cache.delete_key(f"bible_text:{translation}")


# Text files --------------------------------------------------------------------------------------


def load_text(file_url: str | None) -> dict:
	"""Read a translation's text file into {book id: {"name": …, "chapters": {number: [items]}}}."""
	if not file_url:
		frappe.throw(_("This translation has no text yet."))
	content = frappe.get_doc("File", {"file_url": file_url}).get_content()
	try:
		if file_url.lower().endswith(".csv"):
			return _from_csv(content)
		return from_free_use_json(json.loads(content))
	except (KeyError, TypeError, ValueError) as error:
		frappe.throw(_("Could not read {0}: {1}").format(file_url, error))


def count_verses(books: dict) -> int:
	return sum(
		item["type"] == "verse"
		for book in books.values()
		for items in book["chapters"].values()
		for item in items
	)


def download_free_use_bible(source_id: str) -> dict:
	"""A whole translation from the Free Use Bible API, without its audio data."""
	response = requests.get(f"{FREE_USE_BIBLE_API_URL}/{source_id}/complete.simple.json", timeout=300)
	response.raise_for_status()
	data = response.json()
	for book in data["books"]:
		for chapter in book["chapters"]:
			chapter.pop("thisChapterAudioLinks", None)
			chapter.pop("thisChapterAudioTimings", None)
	return data


def from_free_use_json(data: dict) -> dict:
	return {
		book["id"]: {
			"name": book.get("commonName") or book.get("name") or book["id"],
			"chapters": {
				chapter["chapter"]["number"]: chapter["chapter"]["content"] for chapter in book["chapters"]
			},
		}
		for book in data["books"]
	}


def _from_csv(content: str) -> dict:
	"""Rows of book, chapter, verse and text, where the book is a USFM id (JHN) or a name (John)."""
	reader = csv.DictReader(io.StringIO(content))
	reader.fieldnames = [name.strip().lower() for name in reader.fieldnames or ()]
	if set(CSV_COLUMNS) - set(reader.fieldnames):
		frappe.throw(_("A CSV text file needs the columns book, chapter, verse and text."))
	books = {}
	for row in reader:
		try:
			chapter, verse, text = int(row["chapter"]), int(row["verse"]), row["text"].strip()
		except (AttributeError, TypeError, ValueError):
			frappe.throw(
				_("Line {0} of the text file needs a chapter, verse and text.").format(reader.line_num)
			)
		number = _book_number(row["book"] or "")
		book = books.setdefault(
			USFM_BOOKS[number - 1], {"name": pythonbible.Book(number).title, "chapters": {}}
		)
		book["chapters"].setdefault(chapter, []).append({"type": "verse", "number": verse, "text": text})
	return books


def _book_number(name: str) -> int:
	"""1 for Genesis through 66 for Revelation, from a USFM id or any name pythonbible knows."""
	name = name.strip()
	if name.upper() in USFM_BOOKS:
		return USFM_BOOKS.index(name.upper()) + 1
	references = pythonbible.get_references(f"{name} 1:1")
	if not references or references[0].book.value > len(USFM_BOOKS):
		frappe.throw(_("Unknown book in the text file: {0}").format(name))
	return references[0].book.value
