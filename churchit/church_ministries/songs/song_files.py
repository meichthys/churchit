# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Song files: import ChordPro and SongSelect `.usr` files as Songs.

An imported file becomes a Song with one Default arrangement and its slides. A file is skipped when
the importer already lists a Song with its CCLI number, or with its title when it has none. The
public-domain hymns shipped in `hymns/` import the same way, and are never fetched at run time.
"""

import os
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from churchit.church_ministries.doctype.song.song import make_slides
from churchit.church_ministries.songs import chordpro
from churchit.church_people.list_actions import parse_names

DEFAULT_ARRANGEMENT = "Default"
CHORDPRO_EXTENSIONS = (".cho", ".chordpro", ".chopro", ".pro")
SONGSELECT_EXTENSION = ".usr"
MAX_IMPORT_FILES = 50
MAX_FILE_SIZE = 1024 * 1024
# Frappe's default list tries windows-1250 first, which garbles Western ANSI song files.
TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "windows-1252")
AUTHOR_DIRECTIVES = ("artist", "author", "lyricist", "composer")
THEME_DIRECTIVES = ("tag", "theme")
# A theme becomes a Tag, which the desk list shows unescaped and splits on commas.
PLAIN_THEME = re.compile(r"[\w .&/()-]+")
SONGSELECT_CCLI = re.compile(r"\[S A?(\d+)\]")
HYMNS_FOLDER = os.path.join(os.path.dirname(__file__), "hymns")


@frappe.whitelist(methods=["POST"])
def import_song_files(files: str | list[str]) -> frappe._dict:
	"""Import each uploaded File as a Song: `{"imported": [{"file", "song"}], "skipped": [file]}`."""
	names = parse_names(files)
	if len(names) > MAX_IMPORT_FILES:
		frappe.throw(_("Import at most {0} files at a time.").format(MAX_IMPORT_FILES))

	result, uploads = frappe._dict(imported=[], skipped=[]), []
	for name in names:
		file = frappe.get_doc("File", name)
		file.check_permission("read")
		uploads.append(file)
		song = import_song_text(file.file_name, get_file_text(file))
		if song:
			result.imported.append({"file": file.file_name, "song": song})
		else:
			result.skipped.append(file.file_name)

	# The upload only carries the import: drop the caller's own loose Files, never one attached elsewhere.
	for file in uploads:
		if file.owner == frappe.session.user and not file.attached_to_doctype:
			file.delete()
	return result


def get_file_text(file: Document) -> str:
	"""The text of an uploaded File, refused when it is no text file or its size on disk is over the limit."""
	if file.is_folder or file.is_remote_file:
		frappe.throw(_("{0} is not an uploaded file.").format(frappe.bold(file.file_name)))
	file.validate_file_path()
	if os.path.getsize(file.get_full_path()) > MAX_FILE_SIZE:
		frappe.throw(
			_("{0} is larger than {1} MB.").format(
				frappe.bold(file.file_name), f"{MAX_FILE_SIZE / 1048576:g}"
			)
		)

	text = file.get_content(encodings=TEXT_ENCODINGS)
	if not isinstance(text, str):
		frappe.throw(_("{0} is not a text file.").format(frappe.bold(file.file_name)))
	return text


def import_song_text(filename: str, text: str, public_domain: bool = False) -> str | None:
	"""Insert the Song in a ChordPro or `.usr` file and return its name, or None when it is skipped."""
	values = read_song_file(filename, text)
	if is_listed(values):
		return None

	keys = frappe.get_meta("Song").get_options("default_key").split("\n")
	key = values.key if values.key in keys else ""
	song = frappe.get_doc(
		{
			"doctype": "Song",
			"title": values.title,
			"ccli": values.ccli,
			"authors": values.authors,
			"copyright": values.copyright,
			"public_domain": cint(public_domain),
			"default_key": key,
			"tempo": cint(values.tempo),
			"time_signature": values.time_signature,
			"arrangements": [
				{
					"arrangement_name": DEFAULT_ARRANGEMENT,
					"song_key": key,
					"tempo": cint(values.tempo),
					"chordpro": values.chordpro,
				}
			],
		}
	).insert()
	make_slides(song.name, DEFAULT_ARRANGEMENT)
	for theme in dict.fromkeys(values.themes):
		song.add_tag(theme)
	return song.name


def read_song_file(filename: str, text: str) -> frappe._dict:
	"""The Song values in a ChordPro or `.usr` file, refused when it has no words or a value is too long."""
	extension = os.path.splitext(filename)[1].lower()
	if extension in CHORDPRO_EXTENSIONS:
		values = read_chordpro(text)
	elif extension == SONGSELECT_EXTENSION:
		values = read_songselect(text)
	else:
		frappe.throw(_("{0} is not a ChordPro or SongSelect file.").format(frappe.bold(filename)))

	values.title = values.title or os.path.splitext(filename)[0]
	values.authors = ", ".join(dict.fromkeys(values.authors))
	themes = (theme.strip() for theme in values.themes)
	values.themes = [
		theme for theme in themes if PLAIN_THEME.fullmatch(theme) and len(theme) <= frappe.db.VARCHAR_LEN
	]
	if not chordpro.lyrics(values.chordpro):
		frappe.throw(_("{0} has no words.").format(frappe.bold(filename)))
	for label, value in ((_("Title"), values.title), (_("Authors"), values.authors)):
		if len(value) > frappe.db.VARCHAR_LEN:
			frappe.throw(
				_("{0}: {1} is longer than {2} characters.").format(
					frappe.bold(filename), label, frappe.db.VARCHAR_LEN
				)
			)
	return values


def is_listed(values: frappe._dict) -> bool:
	"""Whether the importer lists a Song with this CCLI number, or with this title when it has none."""
	filters = {"ccli": values.ccli} if values.ccli else {"title": values.title}
	return bool(frappe.get_list("Song", filters=filters, limit=1))


def read_chordpro(text: str) -> frappe._dict:
	chart = chordpro.parse(text)
	return frappe._dict(
		title=chart.get("title"),
		ccli=chart.get("ccli"),
		authors=[author for name in AUTHOR_DIRECTIVES for author in chart.meta.get(name, [])],
		copyright=chart.get("copyright"),
		key=chart.get("key"),
		tempo=chart.get("tempo"),
		time_signature=chart.get("time"),
		themes=[theme for name in THEME_DIRECTIVES for theme in chart.meta.get(name, [])],
		chordpro=text,
	)


def read_songselect(text: str) -> frappe._dict:
	"""A SongSelect `.usr` file: `[S A<ccli>]`, then `Name=value` lines.

	`Fields` names the sections and `Words` holds them, both split by `/t`, with `/n` between lines.
	"""
	fields, ccli = {}, ""
	for line in text.splitlines():
		header = SONGSELECT_CCLI.fullmatch(line.strip())
		if header:
			ccli = header.group(1)
		elif "=" in line:
			name, value = line.split("=", 1)
			fields[name.strip()] = value.strip()

	admin = fields.get("Admin")
	return frappe._dict(
		title=fields.get("Title"),
		ccli=ccli,
		authors=split_list(fields.get("Author"), "|"),
		copyright="\n".join(filter(None, [fields.get("Copyright"), admin and f"Administered by {admin}"])),
		key=(split_list(fields.get("Keys"), "/t") or [""])[0],
		themes=split_list(fields.get("Themes"), "/t"),
		chordpro=songselect_chart(fields),
	)


def songselect_chart(fields: dict) -> str:
	"""The words of a `.usr` file as a ChordPro chart with no chords, one block per section."""
	labels = split_list(fields.get("Fields"), "/t")
	sections = [f"{{title: {fields['Title']}}}"] if fields.get("Title") else []
	for index, words in enumerate((fields.get("Words") or "").split("/t")):
		label = labels[index] if index < len(labels) else ""
		kind = chordpro.kind_of_label(label)
		block = kind if kind != "other" else "part"
		start = f"start_of_{block}: {label}" if label else f"start_of_{block}"
		lines = "\n".join(line.strip() for line in words.split("/n"))
		sections.append(f"{{{start}}}\n{lines}\n{{end_of_{block}}}")
	return "\n\n".join(sections) + "\n"


def split_list(value: str | None, separator: str) -> list[str]:
	return [part.strip() for part in (value or "").split(separator) if part.strip()]


@frappe.whitelist(methods=["GET"])
def get_public_domain_hymns() -> list[dict]:
	"""The hymns shipped in `hymns/`, by title, for a checklist: `[{"file", "title", "authors"}]`."""
	frappe.has_permission("Song", "create", throw=True)
	hymns = []
	for filename in get_hymn_files():
		values = read_song_file(filename, read_hymn(filename))
		hymns.append({"file": filename, "title": values.title, "authors": values.authors})
	return sorted(hymns, key=lambda hymn: hymn["title"])


@frappe.whitelist(methods=["POST"])
def add_public_domain_hymns(files: str | list[str]) -> frappe._dict:
	"""Import each shipped hymn as a public-domain Song: `{"imported": [{"file", "song"}], "skipped": [file]}`."""
	frappe.has_permission("Song", "create", throw=True)
	shipped, result = get_hymn_files(), frappe._dict(imported=[], skipped=[])
	for filename in parse_names(files):
		if filename not in shipped:
			frappe.throw(_("{0} is not a shipped hymn.").format(frappe.bold(filename)))
		song = import_song_text(filename, read_hymn(filename), public_domain=True)
		if song:
			result.imported.append({"file": filename, "song": song})
		else:
			result.skipped.append(filename)
	return result


def get_hymn_files() -> list[str]:
	return sorted(name for name in os.listdir(HYMNS_FOLDER) if name.endswith(".cho"))


def read_hymn(filename: str) -> str:
	with open(os.path.join(HYMNS_FOLDER, filename), encoding="utf-8") as file:
		return file.read()
