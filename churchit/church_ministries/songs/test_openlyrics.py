# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import io
import xml.etree.ElementTree as ElementTree
import zipfile

import frappe

from churchit.church_ministries.doctype.song.test_song import CHART, make_song
from churchit.church_ministries.songs.openlyrics import NAMESPACE, to_openlyrics
from churchit.church_ministries.songs.song_files import export_songs
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches

VERSE_AND_CHORUS = """{title: _Test Export}
{start_of_verse: Verse 1}
[G]Amazing [D/F#]grace, how <sweet> the [G]sound
That [C]saved a wretch like [G]me
{end_of_verse}

{start_of_chorus}
[C]My chains are [G]gone
{end_of_chorus}
"""


def find(element, path):
	return element.find(path.replace("ol:", f"{{{NAMESPACE}}}"))


def bind(email, role, church):
	user = ensure_user(email, "SongExportTest", roles=(role,))
	if not frappe.db.exists("Person", {"user": user}):
		make_person("_Test Song Export", role, church=church, user=user)
	return user


class TestOpenLyrics(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.staff_a = bind("_test_song_export_staff_a@example.com", "Church Staff", cls.branch_a)
		cls.manager_b = bind("_test_song_export_manager_b@example.com", "Church Manager", cls.branch_b)
		cls.song = make_song(
			"_Test Export Amazing Grace",
			cls.branch_a,
			ccli="4755360",
			authors="John Newton, John P. Rees",
			copyright="Public Domain",
			tempo=72,
		)
		cls.song.arrangements[0].chordpro = VERSE_AND_CHORUS
		cls.song.save(ignore_permissions=True)

	def export(self, songs, file_format):
		for key in ("type", "filename", "filecontent"):
			self.addCleanup(frappe.local.response.pop, key, None)
		export_songs(frappe.as_json(songs), file_format)
		return frappe.local.response.filename, frappe.local.response.filecontent

	def test_the_xml_is_openlyrics_with_verses_and_no_chords(self):
		root = ElementTree.fromstring(to_openlyrics(self.song, self.song.arrangements[0]))

		self.assertEqual((root.tag, root.get("version")), (f"{{{NAMESPACE}}}song", "0.9"))
		self.assertEqual(find(root, "ol:properties/ol:titles/ol:title").text, "_Test Export Amazing Grace")
		authors = root.findall(f"{{{NAMESPACE}}}properties/{{{NAMESPACE}}}authors/{{{NAMESPACE}}}author")
		self.assertEqual([author.text for author in authors], ["John Newton", "John P. Rees"])
		self.assertEqual(find(root, "ol:properties/ol:ccliNo").text, "4755360")
		self.assertEqual(find(root, "ol:properties/ol:key").text, "G")
		self.assertEqual(find(root, "ol:properties/ol:tempo").attrib, {"type": "bpm"})
		self.assertEqual(find(root, "ol:properties/ol:verseOrder").text, "v1 c1")

		verses = root.findall(f"{{{NAMESPACE}}}lyrics/{{{NAMESPACE}}}verse")
		self.assertEqual([verse.get("name") for verse in verses], ["v1", "c1"])
		lines = find(verses[0], "ol:lines")
		self.assertEqual(
			[lines.text, *(br.tail for br in lines)],
			["Amazing grace, how <sweet> the sound", "That saved a wretch like me"],
		)
		self.assertNotIn("[", ElementTree.tostring(root, encoding="unicode"))

	def test_sections_are_numbered_by_kind(self):
		row = frappe._dict(chordpro=CHART + "\n{comment: Verse 2}\n[G]Twas grace\n\nTag\nAmen\n")
		root = ElementTree.fromstring(to_openlyrics(self.song, row))

		names = [verse.get("name") for verse in root.findall(f"{{{NAMESPACE}}}lyrics/{{{NAMESPACE}}}verse")]
		self.assertEqual(names, ["v1", "c1", "b1", "v2", "o1"])

	def test_the_chordpro_export_is_the_arrangements_chart(self):
		frappe.set_user(self.staff_a)

		self.assertEqual(
			self.export([self.song.name], "ChordPro"), ("_Test Export Amazing Grace.cho", VERSE_AND_CHORUS)
		)
		filename, xml = self.export([self.song.name], "OpenLyrics")
		self.assertEqual(filename, "_Test Export Amazing Grace.xml")
		self.assertEqual(ElementTree.fromstring(xml).tag, f"{{{NAMESPACE}}}song")

	def test_two_songs_give_a_zip_with_two_files(self):
		other = make_song("_Test Export Amazing Grace", self.branch_a)

		frappe.set_user(self.staff_a)
		filename, content = self.export([self.song.name, other.name], "OpenLyrics")
		self.assertEqual(filename, "Songs.zip")
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertEqual(
				archive.namelist(),
				["_Test Export Amazing Grace.xml", f"_Test Export Amazing Grace {other.name}.xml"],
			)
			for name in archive.namelist():
				ElementTree.fromstring(archive.read(name))

	def test_a_song_with_no_arrangement_is_listed_as_skipped(self):
		bare = frappe.get_doc(
			{"doctype": "Song", "title": "_Test Export No Arrangement", "church": self.branch_a}
		).insert(ignore_permissions=True)

		frappe.set_user(self.staff_a)
		_filename, content = self.export([self.song.name, bare.name], "ChordPro")
		with zipfile.ZipFile(io.BytesIO(content)) as archive:
			self.assertEqual(archive.namelist(), ["_Test Export Amazing Grace.cho", "Skipped Songs.txt"])
			self.assertIn("_Test Export No Arrangement", archive.read("Skipped Songs.txt").decode())
		with self.assertRaisesRegex(frappe.ValidationError, "has an arrangement"):
			self.export([bare.name], "ChordPro")

	def test_an_arrangement_with_no_words_is_passed_over(self):
		song = make_song("_Test Export Chords Only", self.branch_a)
		song.arrangements[0].chordpro = "{title: _Test Export Chords Only}\n[G] [C]\n"
		song.append("arrangements", {"arrangement_name": "_Test Words", "chordpro": VERSE_AND_CHORUS})
		song.save(ignore_permissions=True)

		frappe.set_user(self.staff_a)
		self.assertEqual(self.export([song.name], "ChordPro")[1], VERSE_AND_CHORUS)

	def test_at_most_200_songs_export_at_once(self):
		frappe.set_user(self.staff_a)

		with self.assertRaisesRegex(frappe.ValidationError, "at most 200"):
			self.export([f"SONG-{number}" for number in range(201)], "ChordPro")

	def test_an_unknown_format_is_refused(self):
		frappe.set_user(self.staff_a)

		with self.assertRaises(frappe.ValidationError):
			self.export([self.song.name], "OpenSong")

	def test_another_church_cannot_export_an_unshared_song(self):
		frappe.set_user(self.manager_b)

		with self.assertRaises(frappe.PermissionError):
			self.export([self.song.name], "ChordPro")
