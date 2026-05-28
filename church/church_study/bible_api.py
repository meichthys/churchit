# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import re

import frappe
import requests
from frappe import _

HELLOAO_BASE = "https://bible.helloao.org/api"
HTTP_TIMEOUT = 20


def _http_get_json(url):
	try:
		resp = requests.get(url, timeout=HTTP_TIMEOUT)
	except requests.RequestException as exc:
		frappe.throw(
			_("Could not reach bible.helloao.org. Please try again later. ({0})").format(str(exc))
		)
	if not resp.ok:
		frappe.throw(
			_("bible.helloao.org returned an error ({0}) for {1}").format(resp.status_code, url)
		)
	try:
		return resp.json()
	except ValueError:
		frappe.throw(_("bible.helloao.org returned an unexpected response."))


def _person_link(name, label=None):
	from urllib.parse import quote

	from frappe.utils import escape_html

	display = escape_html(label or name)
	return f'<a href="/app/person/{quote(name)}">{display}</a>'


def _resolve_translation_id(translation_name):
	if not translation_name:
		frappe.throw(_("A Bible Translation is required."))
	abbr = frappe.db.get_value("Bible Translation", translation_name, "abbreviation")
	if not abbr:
		frappe.throw(
			_("Translation '{0}' has no abbreviation set.").format(translation_name)
		)
	data = _http_get_json(f"{HELLOAO_BASE}/available_translations.json")
	for t in data.get("translations", []):
		if t.get("shortName") == abbr and t.get("language") == "eng":
			return t.get("id")
	frappe.throw(
		_(
			"Translation '{0}' is not available from bible.helloao.org. "
			"It may be copyrighted. See https://copy.church/initiatives/bibles/ for free alternatives."
		).format(abbr)
	)


def _resolve_book_id(translation_id, book_abbreviation):
	if not book_abbreviation:
		frappe.throw(_("Book has no abbreviation set."))
	data = _http_get_json(f"{HELLOAO_BASE}/{translation_id}/books.json")
	for b in data.get("books", []):
		if b.get("id") == book_abbreviation or b.get("shortName") == book_abbreviation:
			return b.get("id"), b
	frappe.throw(
		_("Book '{0}' not found in translation '{1}'.").format(book_abbreviation, translation_id)
	)


def _book_abbreviation(book_name):
	abbr = frappe.db.get_value("Bible Book", book_name, "abbreviation")
	if not abbr:
		frappe.throw(_("Bible Book '{0}' is missing an abbreviation.").format(book_name))
	return abbr


def _flatten_verse_content(content):
	if not isinstance(content, list):
		return str(content or "").strip()
	parts = []
	for item in content:
		if isinstance(item, str):
			parts.append(item)
		elif isinstance(item, dict) and item.get("text"):
			parts.append(item["text"])
	return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _fetch_chapter(translation_id, book_id, chapter):
	return _http_get_json(f"{HELLOAO_BASE}/{translation_id}/{book_id}/{int(chapter)}.json")


def _get_or_create_bible_verse(book, chapter, verse):
	verse = str(int(verse))
	chapter = str(int(chapter))
	name = f"{book} {chapter}:{verse}"
	if frappe.db.exists("Bible Verse", name):
		return name
	doc = frappe.get_doc(
		{
			"doctype": "Bible Verse",
			"book": book,
			"chapter": chapter,
			"verse": verse,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


@frappe.whitelist()
def get_chapters_for_book(book, translation):
	"""Return [1..N] chapter numbers available for `book` in `translation`."""
	translation_id = _resolve_translation_id(translation)
	book_abbr = _book_abbreviation(book)
	_book_id, book_meta = _resolve_book_id(translation_id, book_abbr)
	num_chapters = book_meta.get("numberOfChapters") or book_meta.get("totalChapters")
	if not num_chapters:
		frappe.throw(_("Could not determine chapter count for '{0}'.").format(book))
	return list(range(1, int(num_chapters) + 1))


@frappe.whitelist()
def get_verses_for_chapter(book, chapter, translation):
	"""Return verse numbers present in (book, chapter) for `translation`."""
	translation_id = _resolve_translation_id(translation)
	book_abbr = _book_abbreviation(book)
	book_id, _meta = _resolve_book_id(translation_id, book_abbr)
	data = _fetch_chapter(translation_id, book_id, chapter)
	chapter_obj = data.get("chapter") or {}
	verses = []
	for item in chapter_obj.get("content") or []:
		if isinstance(item, dict) and item.get("type") == "verse":
			try:
				verses.append(int(item.get("number")))
			except (TypeError, ValueError):
				continue
	return sorted(set(verses))


@frappe.whitelist()
def get_or_create_reference(book, chapter, start_verse_num, end_verse_num, translation):
	"""Resolve or create a Bible Reference for the given coordinates and
	populate reference_text from helloao.org if missing."""
	if not (book and chapter and start_verse_num and translation):
		frappe.throw(_("Book, chapter, start verse, and translation are all required."))

	chapter_i = int(chapter)
	start_i = int(start_verse_num)
	end_i = int(end_verse_num) if end_verse_num not in (None, "", 0, "0") else None
	if end_i is not None and end_i < start_i:
		frappe.throw(_("End verse must not come before the start verse."))
	if end_i == start_i:
		end_i = None

	start_name = _get_or_create_bible_verse(book, chapter_i, start_i)
	end_name = _get_or_create_bible_verse(book, chapter_i, end_i) if end_i else None

	filters = {
		"start_verse": start_name,
		"end_verse": end_name,
		"translation": translation,
	}
	existing = frappe.db.get_value("Bible Reference", filters, "name")
	if existing:
		ref_name = existing
	else:
		ref = frappe.get_doc(
			{
				"doctype": "Bible Reference",
				"start_verse": start_name,
				"end_verse": end_name,
				"translation": translation,
			}
		)
		ref.insert(ignore_permissions=True)
		ref_name = ref.name

	current_text = frappe.db.get_value("Bible Reference", ref_name, "reference_text")
	if not current_text:
		fetch_reference_text(ref_name)

	return ref_name


@frappe.whitelist()
def assign_memory(references, users=None, group=None):
	"""Assign Bible References to users for memorization. Creates a
	Bible Memory Item for each (reference, user) pair that doesn't
	already exist. Pass either ``users`` or ``group`` (expands to all
	members of the group with a linked App User). Restricted to Church
	Manager / System Manager."""
	import json as _json

	def _coerce(val):
		if isinstance(val, list):
			return val
		if isinstance(val, str):
			val = val.strip()
			if val.startswith("["):
				return _json.loads(val)
			return [val] if val else []
		return []

	references = _coerce(references)
	users = _coerce(users)

	missing_users = []
	if group and not users:
		rows = frappe.db.sql(
			"""
			SELECT p.name, p.full_name, p.user
			FROM `tabGroup Member` gm
			INNER JOIN `tabPerson` p ON p.name = gm.person
			WHERE gm.parent = %s
				AND gm.parenttype = 'Group'
			""",
			group,
			as_dict=True,
		)
		users = [r.user for r in rows if r.user]
		missing_users = [_person_link(r.name, r.full_name) for r in rows if not r.user]

	if not references or not users:
		if missing_users:
			frappe.throw(
				_("No members of this group have linked App Users: {0}").format(
					", ".join(missing_users)
				)
			)
		frappe.throw(_("Select at least one reference and one user (or a group with linked App Users)."))

	if not (set(frappe.get_roles()) & {"Church Manager", "System Manager", "Administrator"}):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	assigner = frappe.session.user
	created = 0
	skipped = 0
	for ref in references:
		if not frappe.db.exists("Bible Reference", ref):
			continue
		for user in users:
			if not frappe.db.exists("User", user):
				continue
			if frappe.db.exists(
				"Bible Memory Item", {"user": user, "bible_reference": ref}
			):
				skipped += 1
				continue
			frappe.get_doc(
				{
					"doctype": "Bible Memory Item",
					"user": user,
					"bible_reference": ref,
					"assigned_by": assigner if assigner != user else None,
				}
			).insert(ignore_permissions=True)
			created += 1
	return {"created": created, "skipped": skipped, "missing_users": missing_users}


@frappe.whitelist()
def fetch_reference_text(bible_reference):
	"""Fetch the verses for a Bible Reference from bible.helloao.org and
	cache them on `reference_text`. Returns the fetched text."""
	ref = frappe.get_doc("Bible Reference", bible_reference)
	if not ref.translation:
		frappe.throw(_("Please select a Bible Translation before importing reference text."))
	if not ref.start_verse:
		frappe.throw(_("Reference has no start verse."))

	start_verse = frappe.get_doc("Bible Verse", ref.start_verse)
	end_verse = frappe.get_doc("Bible Verse", ref.end_verse) if ref.end_verse else None

	translation_id = _resolve_translation_id(ref.translation)
	book_abbr = _book_abbreviation(start_verse.book)
	book_id, _meta = _resolve_book_id(translation_id, book_abbr)

	start_chapter = int(start_verse.chapter)
	start_v = int(start_verse.verse)
	end_chapter = int(end_verse.chapter) if end_verse else start_chapter
	end_v = int(end_verse.verse) if end_verse else None

	collected = []
	for ch in range(start_chapter, end_chapter + 1):
		chapter_data = _fetch_chapter(translation_id, book_id, ch)
		content = (chapter_data.get("chapter") or {}).get("content") or []
		verses = []
		for item in content:
			if not (isinstance(item, dict) and item.get("type") == "verse"):
				continue
			try:
				num = int(item.get("number"))
			except (TypeError, ValueError):
				continue
			verses.append({"number": num, "text": _flatten_verse_content(item.get("content"))})

		for v in verses:
			if end_v is None and start_chapter == end_chapter:
				if v["number"] != start_v:
					continue
			else:
				if ch == start_chapter and v["number"] < start_v:
					continue
				if end_v is not None and ch == end_chapter and v["number"] > end_v:
					continue
			collected.append(f"{v['number']}. {v['text']}")

	if not collected:
		frappe.throw(
			_(
				"No verses found in {0} for the specified range. Verify that the "
				"verses exist and are in the same book."
			).format(translation_id)
		)

	text = " ".join(collected).strip()
	frappe.db.set_value("Bible Reference", bible_reference, "reference_text", text)
	return text
