# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Suggest Songs sends a function's sermon and its church's song list, never lyrics, charts or CCLI
numbers, and keeps only songs of that church that the caller may read.

Tests never call a model: runner.start is patched, and the check runs as the caller.
"""

from unittest.mock import patch

import frappe

from churchit.ai import runner
from churchit.ai.test_runner import WRITER, FlowRunnerTestCase, flow_session, staff_user
from churchit.church_ministries import ai
from churchit.church_people.test_ai import AITestCase, as_user, set_ai
from churchit.church_people.test_ai_actions import data_of, prompt_of, run_action
from churchit.tests.helpers import make_function, make_two_churches, pop_logs

LYRICS = "Quillwhistle lyric line"
CHART = "[G]Marrowfen chart line"
CCLI = "98765431"


def make_song(title: str, church: str, **values) -> str:
	"""A Song of *church* with lyrics in its slides and a chart in its arrangement."""
	song = frappe.get_doc(
		{
			"doctype": "Song",
			"title": title,
			"church": church,
			"ccli": CCLI,
			"default_key": "G",
			"arrangements": [{"arrangement_name": "Main", "song_key": "G", "chordpro": CHART}],
			"slides": [{"content": f"<p>{LYRICS}</p>"}],
			**values,
		}
	).insert(ignore_permissions=True)
	return song.name


def make_sermon(title: str, church: str, **values) -> str:
	sermon = {"doctype": "Sermon", "title": title, "church": church, "scripture": "John 3:16", **values}
	return frappe.get_doc(sermon).insert(ignore_permissions=True).name


class SongTestCase(AITestCase):
	def setUp(self):
		super().setUp()
		self.song_a = make_song("_Test AI Grace Song", self.branch_a)
		frappe.get_doc("Song", self.song_a).add_tag("Grace")
		self.song_b = make_song("_Test AI Other Church Song", self.branch_b)
		self.sermon = make_sermon("_Test AI Sermon On Love", self.branch_a)
		self.function = make_function(
			"_Test AI Song Sunday",
			church=self.branch_a,
			schedule=[{"item_type": "Sermon", "item": self.sermon, "description": "Sermon"}],
		).name


class TestSuggestSongs(SongTestCase):
	def test_the_prompt_holds_the_sermon_and_the_churchs_songs_only(self):
		_result, call = run_action(self.manager, ai.suggest_songs, self.function)

		data = data_of(call)
		self.assertIn("_Test AI Grace Song | Grace | G | never", data)
		self.assertIn("John 3:16", data)
		self.assertIn("_Test AI Sermon On Love", data)
		self.assertNotIn("_Test AI Other Church Song", prompt_of(call))
		self.assertEqual(call.kwargs["sends"], ("Sermon", "Song"))
		self.assertEqual(call.kwargs["reference_name"], self.function)
		self.assertIn(f'"function": "{self.function}"', prompt_of(call))

	def test_no_lyrics_slides_arrangement_or_ccli_field_is_read(self):
		real_get_doc, real_get_list = frappe.get_doc, frappe.get_list
		with (
			patch("frappe.get_doc", side_effect=real_get_doc) as get_doc,
			patch("frappe.get_list", side_effect=real_get_list) as get_list,
		):
			_result, call = run_action(self.manager, ai.suggest_songs, self.function)

		for value in (LYRICS, CHART, CCLI, "Main"):
			self.assertNotIn(value, prompt_of(call))
		self.assertNotIn("Song", [each.args[0] for each in get_doc.call_args_list if each.args])
		song_reads = [each.kwargs for each in get_list.call_args_list if each.args[:1] == ("Song",)]
		self.assertTrue(song_reads)
		for read in song_reads:
			self.assertLessEqual(set(read["fields"]), set(ai.SONG_FIELDS))
		self.assertFalse(
			set(ai.SONG_FIELDS) & {"ccli", "slides", "arrangements", "media", "authors", "copyright"}
		)

	def test_a_published_sermon_sends_no_sermon_record_and_each_send_is_logged(self):
		pop_logs("Access Log", {"method": f"AI: {ai.SONG_SUGGESTIONS}"})
		_result, call = run_action(self.manager, ai.suggest_songs, self.function)
		logged = pop_logs("Access Log", {"method": f"AI: {ai.SONG_SUGGESTIONS}"}, "reference_document")
		self.assertEqual(sorted(logged), sorted([self.function, self.sermon]))

		with patch("churchit.church_study.doctype.sermon.sermon.Sermon.is_public", True):
			_result, call = run_action(self.manager, ai.suggest_songs, self.function)
		self.assertEqual(call.kwargs["sends"], ("Song",))

	def test_a_title_not_in_the_song_list_is_dropped_and_at_most_eight_are_kept(self):
		others = [make_song(f"_Test AI Hymn {number}", self.branch_a) for number in range(9)]
		answer = {
			"function": self.function,
			"songs": [
				"_test ai grace song",
				"A Song Nobody Wrote",
				"_Test AI Other Church Song",
				*[f"_Test AI Hymn {number}" for number in range(9)],
			],
		}

		result = as_user(self.manager, ai.check_songs, answer)

		names = [song["name"] for song in result["songs"]]
		self.assertEqual(names, [self.song_a, *others[:7]])
		self.assertNotIn(self.song_b, names)
		self.assertNotIn("A Song Nobody Wrote", [song["title"] for song in result["songs"]])

	def test_an_answer_with_no_real_song_or_for_another_function_is_refused(self):
		function_b = make_function("_Test AI Song Sunday B", church=self.branch_b).name
		for answer in (
			{"function": self.function, "songs": ["A Song Nobody Wrote"]},
			{"function": function_b, "songs": ["_Test AI Other Church Song"]},
			{"function": "FUNC-NONE", "songs": []},
			{"function": [self.function], "songs": ["_Test AI Grace Song"]},
		):
			with self.subTest(answer=answer):
				self.assertRaises(frappe.ValidationError, as_user, self.manager, ai.check_songs, answer)


class TestSongRefusals(SongTestCase):
	def test_a_church_that_keeps_away_is_refused(self):
		frappe.db.set_value("Church", self.branch_a, "keep_away_from_ai", 1)

		self.assertRaises(frappe.PermissionError, run_action, self.manager, ai.suggest_songs, self.function)

	def test_a_kept_away_shared_song_is_left_out(self):
		shared = make_song("_Test AI Shared Song", "", is_shared=1, shared_by_church=self.branch_b)
		_result, call = run_action(self.manager, ai.suggest_songs, self.function)
		self.assertIn("_Test AI Shared Song", data_of(call))

		frappe.db.set_value("Church", self.branch_b, "keep_away_from_ai", 1)
		_result, call = run_action(self.manager, ai.suggest_songs, self.function)
		self.assertNotIn("_Test AI Shared Song", data_of(call))
		self.assertTrue(shared)

	def test_a_user_who_cannot_edit_the_function_another_church_ai_off_and_a_member_are_refused(self):
		function_b = make_function("_Test AI Song Sunday B", church=self.branch_b).name
		self.assertRaises(frappe.PermissionError, run_action, self.staff, ai.suggest_songs, self.function)
		self.assertRaises(frappe.PermissionError, run_action, self.manager, ai.suggest_songs, function_b)
		self.assertRaises(frappe.PermissionError, run_action, self.member, ai.suggest_songs, self.function)
		set_ai(0)
		self.assertRaises(frappe.PermissionError, run_action, self.manager, ai.suggest_songs, self.function)


class TestSongsOnFlow(FlowRunnerTestCase):
	"""The song list is a church record: it needs a No training, Zero retention or Local model. Needs Flow."""

	def test_songs_run_on_writer_and_need_a_model_that_keeps_records(self):
		church_a = make_two_churches()[1]
		manager = staff_user("_test_ai_songs_flow@example.com", church_a, ("Church Manager", "Flow User"))
		make_song("_Test AI Flow Song", church_a)
		function = make_function("_Test AI Flow Sunday", church=church_a).name

		frappe.set_user(manager)
		self.set_labels("May train", "May train")
		self.assertRaises(frappe.PermissionError, ai.suggest_songs, function)
		self.set_labels("No training", "May train")
		with flow_session() as new_session:
			ai.suggest_songs(function)
		self.addCleanup(frappe.cache.delete_value, runner.RUN_KEY + "_test-run")
		self.assertEqual(new_session.call_args.args[0].name, WRITER)
