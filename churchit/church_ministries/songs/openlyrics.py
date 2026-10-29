# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""OpenLyrics 0.9 (openlyrics.org), the song format FreeShow, OpenLP and Quelea read.

Only writes it: the lyrics of one arrangement, without chords, one `verse` per chart section.
"""

import re
import xml.etree.ElementTree as ElementTree

from frappe.model.document import Document

from churchit.church_ministries.songs import chordpro

NAMESPACE = "http://openlyrics.info/namespace/2009/song"
VERSION = "0.9"
VERSE_LETTERS = {"verse": "v", "chorus": "c", "bridge": "b", "other": "o"}
AUTHOR_SEPARATORS = re.compile(r"[,;|]")
# Control characters XML 1.0 cannot hold, even escaped.
NOT_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def to_openlyrics(song: Document, arrangement: Document) -> str:
	"""The arrangement's lyrics, with the song's title, authors, copyright, CCLI number, key and tempo."""
	root = ElementTree.Element("song", xmlns=NAMESPACE, version=VERSION, createdIn="Churchit")
	properties = ElementTree.SubElement(root, "properties")
	add(ElementTree.SubElement(properties, "titles"), "title", song.title)
	authors = [author.strip() for author in AUTHOR_SEPARATORS.split(song.authors or "") if author.strip()]
	if authors:
		element = ElementTree.SubElement(properties, "authors")
		for author in authors:
			add(element, "author", author)
	add(properties, "copyright", song.copyright)
	add(properties, "ccliNo", song.ccli)
	add(properties, "key", arrangement.song_key or song.default_key)
	tempo = arrangement.tempo or song.tempo
	if tempo:
		add(properties, "tempo", str(tempo)).set("type", "bpm")

	verses = get_verses(arrangement.chordpro)
	add(properties, "verseOrder", " ".join(name for name, _lines in verses))
	lyrics = ElementTree.SubElement(root, "lyrics")
	for name, lines in verses:
		add_lines(ElementTree.SubElement(lyrics, "verse", name=name), lines)
	return '<?xml version="1.0" encoding="UTF-8"?>\n' + ElementTree.tostring(root, encoding="unicode")


def get_verses(chart: str) -> list[tuple[str, list[str]]]:
	"""Each section of *chart* named by its kind and number: `v1`, `c1`, `v2`, `b1`, `o1`."""
	counts, verses = {}, []
	for section in chordpro.lyrics(chart):
		letter = VERSE_LETTERS[section["kind"]]
		counts[letter] = counts.get(letter, 0) + 1
		verses.append((f"{letter}{counts[letter]}", section["lines"]))
	return verses


def add_lines(verse: ElementTree.Element, lines: list[str]):
	"""`<lines>first<br/>second</lines>`, the way OpenLyrics 0.8 and later break lines."""
	element = ElementTree.SubElement(verse, "lines")
	element.text = NOT_XML.sub("", lines[0])
	for line in lines[1:]:
		ElementTree.SubElement(element, "br").tail = NOT_XML.sub("", line)


def add(parent: ElementTree.Element, name: str, text: str | None) -> ElementTree.Element | None:
	"""A child element holding *text*, or nothing when *text* is empty."""
	if not text:
		return None
	element = ElementTree.SubElement(parent, name)
	element.text = NOT_XML.sub("", text)
	return element
