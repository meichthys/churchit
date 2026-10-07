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
import re
import unicodedata

import frappe
import pythonbible
import requests
from frappe import _
from frappe.utils import escape_html
from pythonbible.regular_expressions import SCRIPTURE_REFERENCE_REGULAR_EXPRESSION
from pythonbible.roman_numeral_util import convert_all_roman_numerals_to_integers

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
BIBLE_BOOKS = list(pythonbible.Book)[: len(USFM_BOOKS)]
# Characters of verse text shown when a reference field is hovered.
PREVIEW_LENGTH = 600

# Text allowed around passages: separators, "and", and a translation in brackets such as (NIV),
# which is chosen separately.
JOINING_TEXT = re.compile(r"(?:\s|[,;.&-]|\band\b|\([^)]*\))*", re.IGNORECASE)

# Fields holding Bible references: tidied on save, and given suggestions in the desk.
REFERENCE_FIELDS = {
	"Belief": ["bible_references"],
	"Bible Memory Item": ["bible_reference"],
	"Bulletin": ["verse"],
	"Church": ["church_verse"],
	"Sermon Slide": ["scripture"],
}


# References --------------------------------------------------------------------------------------


def parse_reference(text: str) -> list:
	"""The passages a reference names, as pythonbible NormalizedReferences."""
	references, problem = read_reference(text)
	if problem:
		frappe.throw(problem, title=_("Bible Reference"))
	return references


def read_reference(text: str) -> tuple[list, str | None]:
	"""The passages a reference names, and what stops it being read, if anything.

	pythonbible skips whatever it cannot read, so "John 3:16; Mark 16:21" came back as John 3:16
	alone (Mark 16 has 20 verses). Here every part of the text has to be read, and every chapter
	and verse typed has to land in a passage.
	"""
	cleaned = clean_reference_text(text or "")
	matches = list(re.finditer(SCRIPTURE_REFERENCE_REGULAR_EXPRESSION, cleaned))
	if not matches:
		return [], _("Could not read the Bible reference {0}.").format(bold_text(text))
	unread = get_unread_text(cleaned, matches)
	if unread:
		return [], _("Could not read {0} in the Bible reference {1}.").format(
			bold_text(unread), bold_text(text)
		)

	references = []
	for match in matches:
		passages = read_passage(match[0])
		if not passages:
			return [], describe_missing_passage(match[0])
		references.extend(passages)
	outside = next((r.book for r in references if (r.end_book or r.book).value > len(USFM_BOOKS)), None)
	if outside:
		return [], _("{0} is outside the 66 books of the Bible, which is not supported yet.").format(
			frappe.bold(outside.title)
		)
	return references, None


def clean_reference_text(text: str) -> str:
	"""Roman numerals as digits and every kind of dash as a hyphen, the way pythonbible reads them."""
	text = convert_all_roman_numerals_to_integers(text)
	return "".join("-" if unicodedata.category(char) == "Pd" else char for char in text)


def get_unread_text(text: str, matches: list) -> str | None:
	"""The first stretch of text around the matched passages that is more than a separator."""
	starts = [0, *(match.end() for match in matches)]
	ends = [*(match.start() for match in matches), len(text)]
	gaps = (text[start:end] for start, end in zip(starts, ends, strict=True))
	return next((gap.strip() for gap in gaps if not JOINING_TEXT.fullmatch(gap)), None)


def read_passage(passage: str) -> list:
	"""What pythonbible reads in one matched reference, or nothing when it dropped any number typed."""
	try:
		references = pythonbible.normalize_reference(passage)
	except (pythonbible.InvalidBookError, pythonbible.InvalidChapterError, pythonbible.InvalidVerseError):
		return []
	typed = {int(number) for number in re.findall(r"\d+", passage)}
	return references if typed <= get_passage_numbers(references) else []


def get_passage_numbers(references) -> set[int]:
	"""Every chapter and verse number in the references, and the number in a book's name (1 John)."""
	numbers = set()
	for reference in references:
		numbers.update(
			(reference.start_chapter, reference.start_verse, reference.end_chapter, reference.end_verse)
		)
		for book in (reference.book, reference.end_book):
			numbers.update(int(number) for number in re.findall(r"\d+", book.title if book else ""))
	return numbers - {None}


def describe_missing_passage(passage: str) -> str:
	"""Why a reference that reads like a passage is not one, as far as its book's size can tell."""
	message = _("{0} is not in the Bible.").format(bold_text(passage.strip()))
	hint = get_book_size_hint(passage)
	return f"{message} {hint}" if hint else message


def get_book_size_hint(passage: str) -> str | None:
	"""How many chapters, or how many verses in the chapter, the passage's book has, if it asks for more."""
	book, rest = split_book(passage)
	if not book:
		return None
	chapters = pythonbible.get_number_of_chapters(book)
	if chapters == 1 and ":" not in rest:
		rest = f"1:{rest}"
	numbers = [int(number) for number in re.findall(r"\d+", rest)]
	if not numbers or rest.count(":") > 1:
		return None
	if (numbers[0] if ":" in rest else max(numbers)) > chapters:
		return describe_chapter_count(book, chapters)
	verses = pythonbible.get_number_of_verses(book, numbers[0]) if ":" in rest else 0
	if max(numbers[1:], default=0) > verses > 0:
		return _("{0} {1} has {2} verses.").format(book.title, numbers[0], verses)
	return None


def describe_chapter_count(book, chapters: int) -> str:
	if chapters == 1:
		return _("{0} has only one chapter.").format(book.title)
	return _("{0} has {1} chapters.").format(book.title, chapters)


def split_book(passage: str) -> tuple:
	"""The book a passage starts with, and the text after its name."""
	for book in BIBLE_BOOKS:
		found = re.match(rf"\s*(?:{book.regular_expression})\b\.?", passage, re.IGNORECASE)
		if found:
			return book, passage[found.end() :]
	return None, passage


def bold_text(text: str) -> str:
	"""Typed text in bold, escaped, for a message the desk shows as HTML."""
	return frappe.bold(escape_html(text or ""))


def format_reference(text: str | None) -> str | None:
	"""Tidy a typed reference for storage, keeping the order and the chapter form typed:
	"jn 3:16; ps 23" becomes "John 3:16; Psalms 23", not reordered or expanded into verses."""
	if not text:
		return text
	return format_references(parse_reference(text))


def format_references(references: list) -> str:
	return "; ".join(_format_one_reference(reference) for reference in references)


@frappe.whitelist()
def check_reference(text: str) -> dict:
	"""The reference as it will be saved, or why it cannot be, for checking a field as it is typed."""
	references, problem = read_reference(text)
	return {"problem": problem} if problem else {"reference": format_references(references)}


@frappe.whitelist()
def get_reference_outline() -> list[dict]:
	"""Each book's title, the names a reader may type for it, and its verse count per chapter."""
	return [
		{
			"title": book.title,
			"names": [book.title, *(f"{get_book_number(book)}{name}" for name in book.abbreviations)],
			"verses": [
				pythonbible.get_number_of_verses(book, chapter)
				for chapter in range(1, pythonbible.get_number_of_chapters(book) + 1)
			],
		}
		for book in BIBLE_BOOKS
	]


def extend_bootinfo(bootinfo):
	"""Tell the desk which fields hold Bible references."""
	bootinfo.bible_reference_fields = REFERENCE_FIELDS


def get_book_number(book) -> str:
	"""The "1 " of 1 John, which pythonbible leaves out of the book's abbreviations."""
	found = re.match(r"\d\s", book.title)
	return found[0] if found else ""


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
	return list(iter_passage(reference, translation))


def iter_passage(reference: str, translation: str | None = None):
	"""The entries of get_passage, reading each chapter only when it is reached."""
	for (book, chapter), numbers in get_verses_by_chapter(reference).items():
		text = {
			item["number"]: item["text"]
			for item in get_chapter(book, chapter, translation)
			if item["type"] == "verse"
		}
		verses = [{"number": number, "text": text[number]} for number in numbers if number in text]
		yield {"book": book, "chapter": chapter, "verses": verses}


def get_passage_text(reference: str, translation: str | None = None, limit: int | None = None) -> str:
	"""A reference's verses as one line of numbered text, for print formats, web pages and memorizing.

	With a limit, the text stops after the verse that passes that many characters, so a preview of
	a whole book reads one chapter rather than all of them.
	"""
	verses, length = [], 0
	for section in iter_passage(reference, translation):
		for verse in section["verses"]:
			verses.append(f"{verse['number']} {' '.join(verse['text'].split())}")
			length += len(verses[-1]) + 1
			if limit and length > limit:
				return " ".join(verses) + " ..."
	return " ".join(verses)


def get_printable_passage(
	reference: str | None, church: str | None = None, translation: str | None = None, limit: int | None = None
):
	"""A reference, with its text in the translation given or else the church's, when the reader may see it."""
	if not reference:
		return None
	translation = translation or get_default_translation(church)
	if not is_readable(translation):
		return frappe._dict(reference=reference, text=None)
	return frappe._dict(
		reference=f"{reference} ({translation})", text=get_passage_text(reference, translation, limit)
	)


@frappe.whitelist()
def get_reference_preview(text: str, church: str | None = None, translation: str | None = None) -> dict:
	"""A reference and the start of its text, for showing when a reference field is hovered.

	The church is the record's; a reader who cannot open it gets their own church's translation.
	"""
	references, problem = read_reference(text)
	if problem:
		return {"problem": problem}
	if church and not (frappe.db.exists("Church", church) and frappe.has_permission("Church", doc=church)):
		church = None
	return get_printable_passage(format_references(references), church, translation, PREVIEW_LENGTH)


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
