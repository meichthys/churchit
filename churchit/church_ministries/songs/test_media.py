# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Rehearsal media reach only the team members who serve at a function with the song."""

from urllib.parse import parse_qs, urlparse

import frappe
from frappe.utils import add_days, getdate

from churchit.church_ministries.songs.media import get_team_song_file
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_team_assignment,
	make_team_position,
)
from churchit.www import ministry_team


def make_song_with_media(title):
	song = frappe.get_doc(
		{"doctype": "Song", "title": title, "arrangements": [{"arrangement_name": "_Test Media Band"}]}
	).insert(ignore_permissions=True)
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.scrub(title)}.txt",
			"content": f"{title} chart",
			"is_private": 1,
			"attached_to_doctype": "Song",
			"attached_to_name": song.name,
		}
	).insert(ignore_permissions=True)
	song.append(
		"media", {"media_type": "Chord Chart", "file": file.file_url, "arrangement": "_Test Media Band"}
	)
	song.append(
		"media", {"media_type": "Video", "label": "_Test Rehearsal Video", "url": "https://example.com/v"}
	)
	song.save(ignore_permissions=True)
	return song, file


class TestSongMediaRows(RollbackEachTest):
	def test_a_media_row_of_an_unknown_arrangement_fails_to_save(self):
		song = frappe.get_doc(
			{
				"doctype": "Song",
				"title": "_Test Media Unknown",
				"arrangements": [{"arrangement_name": "_Test Media Band"}],
				"media": [
					{"media_type": "Audio", "url": "https://example.com/a", "arrangement": "_Test Other"}
				],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			song.insert(ignore_permissions=True)


class TestTeamSongFile(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = ensure_user("_test_media_member@example.com", "Media")
		cls.member = make_person("_Test Media", "Member", user=cls.email)
		cls.stranger = make_person("_Test Media", "Stranger")
		cls.position = make_team_position("_Test Media Singer", [cls.member.name, cls.stranger.name])
		cls.song, cls.file = make_song_with_media("_Test Media Hymn")
		cls.addClassCleanup(frappe.delete_doc, "File", cls.file.name, force=True, ignore_permissions=True)
		cls.other_song, other_file = make_song_with_media("_Test Media Other Hymn")
		cls.addClassCleanup(frappe.delete_doc, "File", other_file.name, force=True, ignore_permissions=True)
		cls.function = cls.make_service("_Test Media Service", 4)
		cls.mine = make_team_assignment(cls.function.name, cls.position.name, cls.member.name)
		cls.theirs = make_team_assignment(cls.function.name, cls.position.name, cls.stranger.name)

	@classmethod
	def make_service(cls, name, days_from_today, songs=None):
		return make_function(
			name,
			start_date=add_days(getdate(), days_from_today),
			schedule=[{"item_type": "Song", "item": song.name} for song in (songs or [cls.song])],
		)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		frappe.local.response = frappe._dict()

	def tearDown(self):
		frappe.local.response = frappe._dict()
		super().tearDown()

	def media(self, song, media_type):
		return next(row.name for row in song.media if row.media_type == media_type)

	def download(self, assignment, media, user=None):
		frappe.set_user(user or self.email)
		get_team_song_file(assignment.name, media)
		return frappe.local.response

	def assert_refused(self, assignment, media, user=None):
		with self.assertRaises(frappe.PermissionError):
			self.download(assignment, media, user)

	def test_a_member_gets_the_file_of_a_song_at_a_function_they_serve_at(self):
		response = self.download(self.mine, self.media(self.song, "Chord Chart"))

		self.assertEqual(response.type, "download")
		self.assertEqual(response.filename, self.file.file_name)
		self.assertEqual(frappe.safe_decode(response.filecontent), "_Test Media Hymn chart")

	def test_a_media_link_without_a_file_redirects_to_its_url(self):
		response = self.download(self.mine, self.media(self.song, "Video"))

		self.assertEqual((response.type, response.location), ("redirect", "https://example.com/v"))

	def test_a_song_that_is_not_on_the_function_is_refused(self):
		self.assert_refused(self.mine, self.media(self.other_song, "Chord Chart"))

	def test_another_persons_assignment_is_refused(self):
		self.assert_refused(self.theirs, self.media(self.song, "Chord Chart"))

	def test_a_declined_assignment_is_refused(self):
		frappe.db.set_value("Ministry Team Assignment", self.mine.name, "status", "Declined")
		self.assert_refused(self.mine, self.media(self.song, "Chord Chart"))

	def test_a_guest_is_refused(self):
		self.assert_refused(self.mine, self.media(self.song, "Chord Chart"), user="Guest")

	def test_a_function_that_ended_more_than_a_week_ago_is_refused(self):
		recent = self.make_service("_Test Media Last Week", -7)
		ended = self.make_service("_Test Media Long Ago", -8)
		media = self.media(self.song, "Chord Chart")

		self.download(make_team_assignment(recent.name, self.position.name, self.member.name), media)
		self.assert_refused(make_team_assignment(ended.name, self.position.name, self.member.name), media)

	def test_the_ministry_team_page_lists_the_media_of_each_song(self):
		frappe.set_user(self.email)
		rows = ministry_team_context().schedules[self.function.name].rows

		links = [(media.label, parse_qs(urlparse(media.url).query)) for media in rows[0].media]
		self.assertEqual(
			links,
			[
				(
					"Chord Chart",
					{"assignment": [self.mine.name], "media": [self.media(self.song, "Chord Chart")]},
				),
				(
					"_Test Rehearsal Video",
					{"assignment": [self.mine.name], "media": [self.media(self.song, "Video")]},
				),
			],
		)
		self.assertTrue(all(media.url.startswith("/api/method/") for media in rows[0].media))

	def test_the_ministry_team_page_lists_no_media_for_a_declined_assignment(self):
		frappe.db.set_value("Ministry Team Assignment", self.mine.name, "status", "Declined")

		frappe.set_user(self.email)
		rows = ministry_team_context().schedules[self.function.name].rows

		self.assertFalse(rows[0].media)


def ministry_team_context():
	context = frappe._dict()
	ministry_team.get_context(context)
	return context
