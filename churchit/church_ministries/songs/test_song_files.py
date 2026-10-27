# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import os
from unittest.mock import patch

import frappe

from churchit.church_ministries.songs import song_files
from churchit.church_ministries.songs.song_files import import_song_files, import_song_text
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

TEST_FILES = os.path.join(os.path.dirname(__file__), "test_files")
SONGSELECT_FILE = "it_is_well.usr"
SONGSELECT_CCLI = "99925376"
CHORDPRO_FILE = "blessed_assurance.cho"


def read_test_file(filename):
	with open(os.path.join(TEST_FILES, filename), encoding="utf-8", newline="") as file:
		return file.read()


def get_tags(song):
	return sorted(filter(None, frappe.db.get_value("Song", song, "_user_tags").split(",")))


def bind(email, church):
	user = ensure_user(email, "SongFileTest", roles=("Church Manager",))
	if not frappe.db.exists("Person", {"user": user}):
		make_person("_Test Song Files", "Manager", church=church, user=user)
	return user


def upload(case, user, filename, content):
	"""A private File that *user* uploaded, deleted after the class (a rollback leaves it on disk)."""
	frappe.set_user(user)
	file = frappe.get_doc(
		{"doctype": "File", "file_name": filename, "content": content, "is_private": 1}
	).insert()
	frappe.set_user("Administrator")
	case.addClassCleanup(frappe.delete_doc, "File", file.name, force=True, ignore_permissions=True)
	return file.name


class TestSongFileImport(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = bind("_test_song_files_a@example.com", cls.branch_a)
		cls.manager_b = bind("_test_song_files_b@example.com", cls.branch_b)
		cls.files = cls.upload_test_files()
		cls.file_of_b = upload(cls, cls.manager_b, "_test_song_files_b.cho", "{title: B}\nWords of B\n")

	@classmethod
	def upload_test_files(cls):
		return [
			upload(cls, cls.manager_a, name, read_test_file(name))
			for name in (SONGSELECT_FILE, CHORDPRO_FILE)
		]

	def import_as(self, user, filename=SONGSELECT_FILE):
		frappe.set_user(user)
		return import_song_text(filename, read_test_file(filename))

	def test_a_songselect_file_makes_a_song_with_its_details(self):
		song = frappe.get_doc("Song", self.import_as(self.manager_a))

		self.assertEqual(
			(song.title, song.ccli, song.authors, song.copyright, song.default_key, song.church),
			(
				"_Test Song Files It Is Well",
				SONGSELECT_CCLI,
				"Horatio Gates Spafford, Philip Paul Bliss",
				"Public Domain",
				"C",
				self.branch_a,
			),
		)
		[arrangement] = song.arrangements
		self.assertEqual((arrangement.arrangement_name, arrangement.song_key), ("Default", "C"))
		self.assertIn("{start_of_chorus: Chorus 1}\nIt is well with my soul,", arrangement.chordpro)
		self.assertNotIn("[", arrangement.chordpro)
		self.assertEqual(len(song.slides), 3)
		self.assertIn("When peace like a river attendeth my way,<br>", song.slides[0].content)
		self.assertEqual(get_tags(song.name), ["Peace", "Trust"])

	def test_a_chordpro_file_keeps_its_chart(self):
		text = read_test_file(CHORDPRO_FILE)
		song = frappe.get_doc("Song", self.import_as(self.manager_a, CHORDPRO_FILE))

		self.assertEqual(
			(song.title, song.ccli, song.authors, song.default_key, song.tempo, song.time_signature),
			("_Test Song Files Blessed Assurance", "", "Fanny Crosby, Phoebe Palmer Knapp", "D", 100, "9/8"),
		)
		self.assertEqual(song.arrangements[0].chordpro, text)
		self.assertEqual([slide.content.count("<br>") for slide in song.slides], [3, 3])
		self.assertNotIn("[D]", song.slides[1].content)
		self.assertEqual(get_tags(song.name), ["Assurance", "Praise"])

	def test_a_theme_with_markup_or_a_comma_is_left_out(self):
		text = (
			"{title: _Test Song Files Odd Themes}\n"
			'{tag: x" onmouseover="alert(1)}\n{theme: a,b}\n{theme:  Grace }\nHello [G]world\n'
		)

		frappe.set_user(self.manager_a)
		self.assertEqual(get_tags(import_song_text("odd_themes.cho", text)), ["Grace"])

	def test_a_second_import_of_a_file_is_skipped(self):
		self.import_as(self.manager_a)

		self.assertIsNone(self.import_as(self.manager_a))
		self.assertEqual(frappe.db.count("Song", {"ccli": SONGSELECT_CCLI}), 1)

	def test_a_file_without_a_ccli_number_is_skipped_by_title(self):
		self.import_as(self.manager_a, CHORDPRO_FILE)

		self.assertIsNone(self.import_as(self.manager_a, CHORDPRO_FILE))
		self.assertIsNone(
			import_song_text("other.pro", "{title: _Test Song Files Blessed Assurance}\nOther words\n")
		)

	def test_another_churches_unshared_song_does_not_count(self):
		mine = self.import_as(self.manager_a)

		theirs = self.import_as(self.manager_b)
		self.assertTrue(theirs)
		self.assertNotEqual(theirs, mine)
		self.assertEqual(frappe.db.get_value("Song", theirs, "church"), self.branch_b)

		frappe.set_user("Administrator")
		frappe.get_doc("Song", mine).update({"is_shared": 1}).save()
		frappe.delete_doc("Song", theirs)
		self.assertIsNone(self.import_as(self.manager_b))

	def test_a_file_that_is_no_song_is_refused(self):
		frappe.set_user(self.manager_a)

		with self.assertRaisesRegex(frappe.ValidationError, "not a ChordPro or SongSelect file"):
			import_song_text("notes.txt", "Words")
		with self.assertRaisesRegex(frappe.ValidationError, "has no words"):
			import_song_text("empty.cho", "{title: _Test Song Files No Words}\n[G] [C]\n")
		self.assertFalse(frappe.db.exists("Song", {"title": "_Test Song Files No Words"}))

	def test_uploaded_files_import_once_and_are_deleted(self):
		files = self.upload_test_files()
		frappe.set_user(self.manager_a)

		result = import_song_files(files)
		self.assertEqual([row["file"] for row in result.imported], [SONGSELECT_FILE, CHORDPRO_FILE])
		self.assertEqual(frappe.db.get_value("Song", result.imported[0]["song"], "ccli"), SONGSELECT_CCLI)
		self.assertEqual(result.skipped, [])
		self.assertFalse(frappe.db.exists("File", {"name": ("in", files)}))

		again = import_song_files(frappe.as_json(self.upload_test_files()))
		self.assertEqual((again.imported, again.skipped), ([], [SONGSELECT_FILE, CHORDPRO_FILE]))

	def test_an_attached_file_is_kept(self):
		frappe.db.set_value(
			"File", self.files[0], {"attached_to_doctype": "Church", "attached_to_name": self.branch_a}
		)

		frappe.set_user(self.manager_a)
		import_song_files(self.files[:1])
		self.assertTrue(frappe.db.exists("File", self.files[0]))

	def test_at_most_50_files_import_at_once(self):
		frappe.set_user(self.manager_a)

		with self.assertRaisesRegex(frappe.ValidationError, "at most 50"):
			import_song_files([f"_test_file_{number}" for number in range(51)])

	def test_another_users_private_file_is_refused(self):
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.PermissionError):
			import_song_files([self.file_of_b])

	def test_a_file_over_the_size_limit_is_refused(self):
		# The uploader can set the stored size, so the limit reads the size on disk.
		frappe.db.set_value("File", self.files[0], "file_size", 1)

		frappe.set_user(self.manager_a)
		with (
			patch.object(song_files, "MAX_FILE_SIZE", 100),
			self.assertRaisesRegex(frappe.ValidationError, "is larger than"),
		):
			import_song_files(self.files[:1])

	def test_an_ansi_file_reads_as_western_text(self):
		chart = "{title: _Test Song Files Señor}\nSeñor, tu è Jesús\n"
		file = upload(self, self.manager_a, "_test_song_files_ansi.cho", chart.encode("cp1252"))

		frappe.set_user(self.manager_a)
		[row] = import_song_files([file]).imported
		self.assertEqual(frappe.get_doc("Song", row["song"]).arrangements[0].chordpro, chart)

	def test_a_value_longer_than_its_field_is_refused(self):
		authors = " | ".join(f"_Test Song Files Writer {number}" for number in range(9))
		text = f"[S A99925377]\nTitle=_Test Song Files Many Writers\nAuthor={authors}\nWords=Words\n"

		frappe.set_user(self.manager_a)
		with self.assertRaisesRegex(frappe.ValidationError, "Authors is longer than 140"):
			import_song_text("many_writers.usr", text)

	def test_a_user_who_cannot_create_songs_imports_nothing(self):
		user = ensure_user("_test_song_files_member@example.com", "SongFileTest")

		frappe.set_user(user)
		with self.assertRaises(frappe.PermissionError):
			import_song_text(SONGSELECT_FILE, read_test_file(SONGSELECT_FILE))

	def test_a_single_church_site_imports_songs(self):
		force_single_church()

		self.assertTrue(self.import_as(self.manager_a, CHORDPRO_FILE))
		self.assertIsNone(self.import_as(self.manager_a, CHORDPRO_FILE))
