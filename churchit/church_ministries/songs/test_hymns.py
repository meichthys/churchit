# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import os

import frappe

from churchit.church_ministries.songs import chordpro
from churchit.church_ministries.songs.song_files import (
	HYMNS_FOLDER,
	add_public_domain_hymns,
	get_hymn_files,
	get_public_domain_hymns,
	read_hymn,
	read_song_file,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

LAST_YEAR = 1930
LAST_DEATH = 1955
TEST_HYMNS = ["abide-with-me.cho", "rock-of-ages.cho"]


def bind(email, church):
	user = ensure_user(email, "HymnTest", roles=("Church Manager",))
	if not frappe.db.exists("Person", {"user": user}):
		make_person("_Test Hymns", "Manager", church=church, user=user)
	return user


class TestHymnFiles(RollbackEachTest):
	def test_at_least_30_hymns_ship_with_the_notice(self):
		self.assertGreaterEqual(len(get_hymn_files()), 30)
		with open(os.path.join(HYMNS_FOLDER, "LICENSE.txt"), encoding="utf-8") as file:
			notice = file.read()
		self.assertIn("WorshipCommonsContent", notice)
		self.assertIn("MIT License", notice)
		self.assertIn("Copyright (c) 2026 ChurchApps", notice)

	def test_every_hymn_parses_with_its_details(self):
		keys = frappe.get_meta("Song").get_options("default_key").split("\n")
		for filename in get_hymn_files():
			with self.subTest(filename):
				text = read_hymn(filename)
				chart = chordpro.parse(text)
				values = read_song_file(filename, text)

				self.assertEqual(values.title, chart.get("title"))
				self.assertIn(chart.get("key"), keys[1:])
				self.assertTrue(chart.meta.get("author"))
				self.assertTrue(chart.get("source").startswith("WorshipCommons, https://"))
				self.assertTrue(chordpro.lyrics(text))
				self.assertNotIn("other", [section.kind for section in chart.sections])

	def test_every_hymn_is_from_1930_or_earlier_by_authors_who_died_by_1955(self):
		for filename in get_hymn_files():
			with self.subTest(filename):
				chart = chordpro.parse(read_hymn(filename))
				[year] = chart.meta["year"]
				died = chart.meta.get("died", [])

				self.assertLessEqual(int(year), LAST_YEAR)
				self.assertEqual(len(died), len(chart.meta["author"]))
				self.assertTrue(all(int(death) <= LAST_DEATH for death in died))


class TestAddPublicDomainHymns(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = bind("_test_hymns_a@example.com", cls.branch_a)
		cls.manager_b = bind("_test_hymns_b@example.com", cls.branch_b)

	def setUp(self):
		super().setUp()
		titles = [chordpro.parse(read_hymn(name)).get("title") for name in TEST_HYMNS]
		frappe.db.delete("Song", {"title": ("in", titles)})

	def test_the_checklist_lists_every_hymn_with_its_title_and_authors(self):
		frappe.set_user(self.manager_a)
		hymns = get_public_domain_hymns()

		self.assertEqual(sorted(hymn["file"] for hymn in hymns), get_hymn_files())
		self.assertIn(
			{
				"file": "abide-with-me.cho",
				"title": "Abide with Me",
				"authors": "Henry Francis Lyte, William Henry Monk",
			},
			hymns,
		)
		self.assertEqual([hymn["title"] for hymn in hymns], sorted(hymn["title"] for hymn in hymns))

	def test_hymns_import_once_as_public_domain(self):
		frappe.set_user(self.manager_a)
		result = add_public_domain_hymns(frappe.as_json(TEST_HYMNS))

		self.assertEqual([row["file"] for row in result.imported], TEST_HYMNS)
		self.assertEqual(result.skipped, [])
		song = frappe.get_doc("Song", result.imported[0]["song"])
		self.assertEqual(
			(song.title, song.public_domain, song.copyright, song.default_key, song.church),
			("Abide with Me", 1, "Public domain", "Eb", self.branch_a),
		)
		self.assertEqual(song.arrangements[0].chordpro, read_hymn(TEST_HYMNS[0]))
		self.assertEqual(len(song.slides), 5)

		again = add_public_domain_hymns(TEST_HYMNS)
		self.assertEqual((again.imported, again.skipped), ([], TEST_HYMNS))
		self.assertEqual(frappe.db.count("Song", {"title": "Abide with Me"}), 1)

	def test_another_churches_unshared_hymn_does_not_count(self):
		frappe.set_user(self.manager_a)
		add_public_domain_hymns(TEST_HYMNS[:1])

		frappe.set_user(self.manager_b)
		[row] = add_public_domain_hymns(TEST_HYMNS[:1]).imported
		self.assertEqual(frappe.db.get_value("Song", row["song"], "church"), self.branch_b)

	def test_only_shipped_hymn_files_are_read(self):
		frappe.set_user(self.manager_a)

		for name in ("../test_files/blessed_assurance.cho", "LICENSE.txt", "_test_no_hymn.cho"):
			with self.subTest(name), self.assertRaisesRegex(frappe.ValidationError, "not a shipped hymn"):
				add_public_domain_hymns([name])

	def test_a_user_who_cannot_create_songs_gets_no_hymns(self):
		frappe.set_user(ensure_user("_test_hymns_member@example.com", "HymnTest"))

		with self.assertRaises(frappe.PermissionError):
			get_public_domain_hymns()
		with self.assertRaises(frappe.PermissionError):
			add_public_domain_hymns(TEST_HYMNS[:1])

	def test_a_single_church_site_adds_hymns(self):
		force_single_church()
		frappe.set_user(self.manager_a)

		self.assertEqual(len(add_public_domain_hymns(TEST_HYMNS[:1]).imported), 1)
		self.assertEqual(add_public_domain_hymns(TEST_HYMNS[:1]).skipped, TEST_HYMNS[:1])
