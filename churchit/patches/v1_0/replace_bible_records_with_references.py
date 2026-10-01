# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Replace Bible Book, Bible Verse and Bible Reference records with plain-text references.

A field that linked to a Bible Reference now holds the passage as text, such as "Psalms 23:1-6",
and a translation keeps its own text. Each Bible Translation is renamed to its abbreviation; the
default one downloads its text now, the other free ones download the first time a church opens
them, and the rest wait for a church to import theirs.

Migrate removes the retired doctypes after the patches run and keeps their tables, so the old
records stay in the database until someone trims it.
"""

import frappe

from churchit.patches.after_install import (
	FREE_USE_TRANSLATIONS,
	set_default_bible_translation,
	should_skip_download,
)
from churchit.scripture import FREE_USE_BIBLE_API, format_reference

RETIRED_DOCTYPES = ("Bible Book", "Bible Verse", "Bible Reference")
RETIRED_RECORDS = (
	("Number Card", "Bible References"),
	("Number Card", "Bible Verses"),
	("Onboarding Step", "Bible Reference"),
	("Form Tour", "Bible Reference"),
)
# Child tables whose link cannot be left empty, with the text a removed row carried:
# a row pointing at a retired record goes, and its parent keeps a comment saying what it held.
REQUIRED_LINKS = (
	("Prayer Topic", "topic_type", "topic", "prayer"),
	("Church Task Item", "item_type", "item", "notes"),
	("Function Association", "association_type", "association", None),
)
SHIPPED_BELIEF_REFERENCES = (
	"                {% for row in belief.bible_references %}\n"
	'                    <div class="small text-muted">'
	'{{ frappe.db.get_value("Bible Reference", row.reference, "reference") }}</div>\n'
	"                {% endfor %}"
)
BELIEF_REFERENCES = '                <div class="small text-muted">{{ belief.bible_references or "" }}</div>'


def execute():
	renamed = rename_translations()
	set_translation_sources()
	set_default_bible_translation()
	references = read_references(renamed)
	fallback = frappe.db.get_value(
		"Church", {"parent_church": ("is", "not set")}, "default_bible_translation"
	)
	convert_link_fields(references)
	convert_beliefs(references)
	convert_memory_items(references, fallback)
	convert_slides(references)
	convert_schedules(references)
	remove_required_links(references)
	rewrite_beliefs_page()
	for doctype, name in RETIRED_RECORDS:
		frappe.delete_doc(doctype, name, force=True, ignore_missing=True, ignore_permissions=True)


def rename_translations():
	"""Name each translation by its abbreviation, as new ones are. Returns {old name: new name}."""
	renamed = {}
	for name, abbreviation in frappe.get_all(
		"Bible Translation", fields=["name", "abbreviation"], as_list=True
	):
		if not abbreviation or name == abbreviation:
			continue
		if frappe.db.exists("Bible Translation", abbreviation):
			print(f"Bible Translation {name} keeps its name: another translation is named {abbreviation}.")
			continue
		frappe.rename_doc("Bible Translation", name, abbreviation, force=True)
		renamed[name] = abbreviation
	return renamed


def set_translation_sources():
	"""Download the default translation now; the other free ones wait for a church to open them.

	Configured translations (a source already set, or a text file already attached) are left alone.
	"""
	for name in frappe.get_all(
		"Bible Translation",
		filters={"source_id": ("is", "not set"), "text_file": ("is", "not set")},
		pluck="name",
	):
		doc = frappe.get_doc("Bible Translation", name)
		doc.source_id = FREE_USE_TRANSLATIONS.get(name)
		doc.source = FREE_USE_BIBLE_API if doc.source_id else "User Import"
		doc.flags.skip_download = should_skip_download(name, doc.source_id)
		doc.save(ignore_permissions=True)


def read_references(renamed):
	"""Each Bible Reference by name, as (reference text, translation)."""
	if not (frappe.db.table_exists("Bible Reference") and frappe.db.table_exists("Bible Verse")):
		return {}
	Reference = frappe.qb.DocType("Bible Reference")
	First = frappe.qb.DocType("Bible Verse").as_("first_verse")
	Last = frappe.qb.DocType("Bible Verse").as_("last_verse")
	rows = (
		frappe.qb.from_(Reference)
		.join(First)
		.on(First.name == Reference.start_verse)
		.left_join(Last)
		.on(Last.name == Reference.end_verse)
		.select(
			Reference.name,
			Reference.translation,
			First.book,
			First.chapter,
			First.verse,
			Last.book.as_("end_book"),
			Last.chapter.as_("end_chapter"),
			Last.verse.as_("end_verse"),
		)
		.run(as_dict=True)
	)
	return {
		row.name: (tidy(passage_text(row)), renamed.get(row.translation, row.translation)) for row in rows
	}


def passage_text(row):
	"""A Bible Reference's verses written out, such as "Psalms 23:1 - Psalms 23:6"."""
	start = f"{row.book} {row.chapter}:{row.verse}"
	return f"{start} - {row.end_book} {row.end_chapter}:{row.end_verse}" if row.end_book else start


def tidy(text):
	"""The reference as it is now stored, or the text unchanged when pythonbible cannot read it."""
	try:
		return format_reference(text)
	except frappe.ValidationError:
		frappe.clear_last_message()
		print(f"Could not read the Bible reference {text!r}; it is kept as written.")
		return text


def resolve(references, value):
	"""(reference text, translation) for a link to a retired record, or for text already converted."""
	return references.get(value) or (tidy(value), None)


def convert_link_fields(references):
	for doctype, fieldname in (("Church", "church_verse"), ("Bulletin", "verse")):
		for name, value in frappe.get_all(
			doctype, filters={fieldname: ("is", "set")}, fields=["name", fieldname], as_list=True
		):
			frappe.db.set_value(
				doctype, name, fieldname, resolve(references, value)[0], update_modified=False
			)


def convert_beliefs(references):
	"""Join each belief's reference rows into its one Bible References field."""
	if not frappe.db.table_exists("Belief Bible References"):
		return
	passages = {}
	for parent, reference in frappe.db.sql(
		"select parent, reference from `tabBelief Bible References` where parenttype = 'Belief' order by idx"
	):
		passages.setdefault(parent, []).append(resolve(references, reference)[0])
	for belief, texts in passages.items():
		if frappe.db.exists("Belief", belief) and not frappe.db.get_value(
			"Belief", belief, "bible_references"
		):
			value = tidy("; ".join(texts))
			frappe.db.set_value("Belief", belief, "bible_references", value, update_modified=False)


def convert_memory_items(references, fallback):
	for name, value, translation in frappe.get_all(
		"Bible Memory Item", fields=["name", "bible_reference", "translation"], as_list=True
	):
		text, reference_translation = resolve(references, value)
		frappe.db.set_value(
			"Bible Memory Item",
			name,
			{"bible_reference": text, "translation": translation or reference_translation or fallback},
			update_modified=False,
		)


def convert_slides(references):
	"""A slide showing a retired record becomes a Scripture slide."""
	for row in frappe.get_all(
		"Sermon Slide", filters={"slide_type": ("in", RETIRED_DOCTYPES)}, fields=["name", "slide"]
	):
		text, translation = resolve(references, row.slide)
		values = {"slide_type": None, "slide": None, "display_fields": None, "scripture": text}
		frappe.db.set_value(
			"Sermon Slide", row.name, {**values, "translation": translation}, update_modified=False
		)


def convert_schedules(references):
	"""An order of worship item linking a retired record keeps the passage in its description."""
	for row in frappe.get_all(
		"Function Schedule",
		filters={"item_type": ("in", RETIRED_DOCTYPES)},
		fields=["name", "item", "description"],
	):
		text, translation = resolve(references, row.item)
		passage = f"{text} ({translation})" if translation else text
		description = "\n".join(filter(None, [row.description, passage]))
		values = {"item_type": None, "item": None, "description": description}
		frappe.db.set_value("Function Schedule", row.name, values, update_modified=False)


def remove_required_links(references):
	for doctype, type_field, link_field, text_field in REQUIRED_LINKS:
		fields = ["name", "parent", "parenttype", link_field, *filter(None, [text_field])]
		for row in frappe.get_all(doctype, filters={type_field: ("in", RETIRED_DOCTYPES)}, fields=fields):
			passage = resolve(references, row[link_field])[0]
			note = f"Bible References were retired, so the link to {passage} was removed from {doctype}."
			if text_field and row[text_field]:
				note += f" It read: {row[text_field]}"
			frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"reference_doctype": row.parenttype,
					"reference_name": row.parent,
					"content": frappe.utils.escape_html(note),
				}
			).insert(ignore_permissions=True)
			frappe.db.delete(doctype, row.name)


def rewrite_beliefs_page():
	"""Show the belief's references on the shipped beliefs page, unless the church rewrote that part."""
	if not frappe.db.exists("Web Page", "beliefs"):
		return
	page = frappe.get_doc("Web Page", "beliefs")
	html = page.main_section_html or ""
	if SHIPPED_BELIEF_REFERENCES in html:
		page.main_section_html = html.replace(SHIPPED_BELIEF_REFERENCES, BELIEF_REFERENCES)
		page.save(ignore_permissions=True)
	elif "Bible Reference" in html:
		print("Web Page beliefs still reads Bible Reference; show belief.bible_references there instead.")
