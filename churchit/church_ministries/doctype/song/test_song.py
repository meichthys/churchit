# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.desk.doctype.tag.tag import add_tag

from churchit.church_ministries.doctype.song.song import make_slides, render_chord_chart
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

CHART = """{title: Amazing Grace}
{comment: Verse 1}
[G]Amazing [D/F#]grace, how <sweet> the [G]sound

{start_of_chorus}
[C]My chains are [G]gone
{end_of_chorus}

Bridge
[Em]The earth shall [D]soon dissolve
"""


def make_song(title, church, **values):
	return frappe.get_doc(
		{
			"doctype": "Song",
			"title": title,
			"church": church,
			"arrangements": [{"arrangement_name": "Default", "song_key": "G", "chordpro": CHART}],
			"slides": [{"content": "<p>Typed by hand</p>"}],
			**values,
		}
	).insert(ignore_permissions=True)


class TestSong(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager_a = cls.bind("_test_song_manager_a@example.com", "Church Manager", cls.branch_a)
		cls.manager_b = cls.bind("_test_song_manager_b@example.com", "Church Manager", cls.branch_b)
		cls.staff_a = cls.bind("_test_song_staff_a@example.com", "Church Staff", cls.branch_a)
		cls.song = make_song("_Test Song Amazing Grace", cls.branch_a)

	@classmethod
	def bind(cls, email, role, church):
		user = ensure_user(email, "SongTest", roles=(role,))
		if not frappe.db.exists("Person", {"user": user}):
			make_person("_Test Song", role, church=church, user=user)
		return user

	def test_a_song_keeps_its_details(self):
		song = make_song(
			"_Test Song Details", self.branch_a, authors="John Newton", default_key="Em", tempo=72
		)

		song.reload()
		self.assertEqual((song.authors, song.default_key, song.tempo), ("John Newton", "Em", 72))

	def test_a_tag_finds_a_song(self):
		untagged = make_song("_Test Song Untagged", self.branch_a)
		add_tag("Advent", "Song", self.song.name)

		frappe.set_user(self.manager_a)
		found = frappe.get_list("Song", filters={"_user_tags": ("like", "%Advent%")}, pluck="name")
		self.assertIn(self.song.name, found)
		self.assertNotIn(untagged.name, found)

	def test_a_church_keeps_its_ccli_license_number(self):
		church = frappe.get_doc("Church", self.branch_a)
		church.ccli_license_number = "1234567"
		church.save()

		self.assertEqual(frappe.db.get_value("Church", self.branch_a, "ccli_license_number"), "1234567")

	def test_two_arrangements_cannot_share_a_name(self):
		song = frappe.get_doc("Song", self.song.name)
		song.append("arrangements", {"arrangement_name": " default "})

		with self.assertRaises(frappe.UniqueValidationError):
			song.save()

	def test_an_arrangement_without_a_name_gets_the_mandatory_message(self):
		song = frappe.get_doc("Song", self.song.name)
		song.append("arrangements", {"chordpro": "[G]x"})

		with self.assertRaises(frappe.MandatoryError):
			song.save()

	def test_the_chord_chart_is_in_the_arrangements_key_or_the_chosen_one(self):
		frappe.set_user(self.staff_a)

		self.assertIn(">D/F#<", render_chord_chart(self.song.name, "Default"))
		self.assertIn(">E/G#<", render_chord_chart(self.song.name, "Default", "A"))
		self.assertIn("&lt;sweet&gt;", render_chord_chart(self.song.name, "Default"))

	def test_the_chord_chart_refuses_an_unknown_key_or_arrangement(self):
		frappe.set_user(self.manager_a)

		with self.assertRaises(frappe.ValidationError):
			render_chord_chart(self.song.name, "Default", "H")
		with self.assertRaises(frappe.DoesNotExistError):
			render_chord_chart(self.song.name, "Acoustic")
		with self.assertRaisesRegex(frappe.ValidationError, "Choose a major key"):
			render_chord_chart(self.song.name, "Default", "Em")

	def test_the_chord_chart_needs_the_written_key_to_change_key(self):
		song = make_song("_Test Song No Key", self.branch_a)
		song.arrangements[0].song_key = ""
		song.save()

		frappe.set_user(self.manager_a)
		self.assertIn(">D/F#<", render_chord_chart(song.name, "Default"))
		with self.assertRaises(frappe.ValidationError):
			render_chord_chart(song.name, "Default", "A")

	def test_another_church_cannot_read_the_chord_chart(self):
		frappe.set_user(self.manager_b)

		with self.assertRaises(frappe.PermissionError):
			render_chord_chart(self.song.name, "Default")

	def test_make_slides_replaces_the_slides_with_one_per_section(self):
		frappe.set_user(self.manager_a)

		self.assertEqual(make_slides(self.song.name, "Default"), 3)
		slides = [row.content for row in frappe.get_doc("Song", self.song.name).slides]
		self.assertEqual(
			slides,
			[
				"<p>Amazing grace, how &lt;sweet&gt; the sound</p>",
				"<p>My chains are gone</p>",
				"<p>The earth shall soon dissolve</p>",
			],
		)

	def test_only_a_writer_of_the_song_can_make_slides(self):
		for user in (self.staff_a, self.manager_b):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				make_slides(self.song.name, "Default")

		frappe.set_user("Administrator")
		self.assertEqual(
			[row.content for row in frappe.get_doc("Song", self.song.name).slides], ["<p>Typed by hand</p>"]
		)

	def test_a_single_church_site_makes_slides(self):
		force_single_church()
		song = make_song("_Test Song Single Church", None)

		self.assertEqual(make_slides(song.name, "Default"), 3)
