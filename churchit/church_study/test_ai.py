# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Sermon study helpers: what each prompt holds and needs, the refusals, and how answers are checked."""

from unittest import mock

import frappe

from churchit.ai.switch import SETTINGS
from churchit.church_foundations.church_access import set_user_church
from churchit.church_study import ai
from churchit.church_website.published_fields import published_field_map
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_translation,
	make_two_churches,
	pop_logs,
)

STAFF = "_test_study_ai_staff@example.com"
WEBSITE_USER = "_test_study_ai_website_user@example.com"
START = "churchit.ai.runner.start"
TRANSCRIPT = "_Test transcript: as I told Jane at the hospital, grace is a gift."
NOTES = "<p>Grace is a gift. Faith receives it. Read John 3:16.</p>"


class TestStudyHelper(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, _other = make_two_churches()
		frappe.db.set_value("Church", cls.church, "publish", 1)
		ensure_user(STAFF, "Study", ("Church Staff",))
		set_user_church(STAFF, cls.church)
		ensure_user(WEBSITE_USER, "Study Website User", ())
		cls.series = ensure(
			"Sermon Series",
			{"series_name": "_Test Study Series"},
			{"series_name": "_Test Study Series", "church": cls.church},
		)
		cls.draft = cls.make_sermon(
			"_Test Study Draft", notes=NOTES, transcript=TRANSCRIPT, series=cls.series
		)
		cls.published = cls.make_sermon("_Test Study Published", notes=NOTES, publish=1, series=cls.series)
		cls.preached = cls.make_sermon("_Test Study Preached", notes=NOTES, transcript=TRANSCRIPT, publish=1)

	@classmethod
	def make_sermon(cls, title: str, **values) -> str:
		sermon = {
			"doctype": "Sermon",
			"title": title,
			"church": cls.church,
			"scripture": "John 3:16",
			**values,
		}
		return frappe.get_doc(sermon).insert(ignore_permissions=True).name

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, "enabled", 1)
		frappe.set_user(STAFF)

	def run_helper(self, sermon: str, purpose: str) -> mock.MagicMock:
		with mock.patch(START, return_value={"token": "t"}) as start:
			self.assertEqual(ai.study_helper(sermon, purpose), {"token": "t"})
		return start

	def refused(self, sermon: str, purpose: str, error=frappe.ValidationError) -> None:
		with mock.patch(START) as start, self.assertRaises(error):
			ai.study_helper(sermon, purpose)
		start.assert_not_called()

	def access_logs(self, sermon: str) -> int:
		"""The Access Log rows of the study helper for *sermon*, removed: Frappe 17 keeps them past a rollback."""
		return len(pop_logs("Access Log", {"reference_document": sermon, "method": ai.ACCESS_LOG_METHOD}))

	def test_a_draft_sermon_is_a_church_record(self):
		self.access_logs(self.draft)
		start = self.run_helper(self.draft, ai.QUESTIONS)

		prompt = start.call_args.args[1]
		self.assertEqual(start.call_args.kwargs["sends"], ("Sermon",))
		self.assertEqual(start.call_args.kwargs["check"], "churchit.church_study.ai.check_questions")
		self.assertIn(TRANSCRIPT, prompt)
		self.assertIn("Grace is a gift.", prompt)
		self.assertIn('<data source="sermon">', prompt)
		self.assertEqual(prompt.count("Answer with JSON only"), 1)
		self.assertEqual(self.access_logs(self.draft), 1)

	def test_a_published_sermons_notes_are_public(self):
		self.access_logs(self.published)
		start = self.run_helper(self.published, ai.SUMMARY)

		self.assertEqual(start.call_args.kwargs["sends"], ())
		self.assertEqual(start.call_args.kwargs["check"], "churchit.ai.writing.check_text")
		self.assertEqual(self.access_logs(self.published), 0)

	def test_a_transcript_is_a_church_record_even_on_a_published_sermon(self):
		self.assertEqual(self.run_helper(self.preached, ai.SUMMARY).call_args.kwargs["sends"], ("Sermon",))

		start = self.run_helper(self.preached, ai.SOCIAL_POST)
		self.assertEqual(start.call_args.kwargs["sends"], ())
		self.assertNotIn(TRANSCRIPT, start.call_args.args[1])

	def test_a_devotional_and_a_post_are_only_for_a_published_sermon(self):
		self.refused(self.draft, ai.DEVOTIONAL)
		self.refused(self.draft, ai.SOCIAL_POST)
		self.run_helper(self.published, ai.DEVOTIONAL)

	def test_it_never_writes_a_sermon_or_a_prayer(self):
		for purpose in ("sermon", "prayer", "write my sermon"):
			with (
				mock.patch(START) as start,
				self.assertRaisesRegex(frappe.ValidationError, "never a sermon or a prayer"),
			):
				ai.study_helper(self.draft, purpose)
			start.assert_not_called()

	def test_a_series_description_names_the_series_and_its_published_sermons(self):
		prompt = self.run_helper(self.draft, ai.SERIES_DESCRIPTION).call_args.args[1]

		self.assertIn("_Test Study Series", prompt)
		self.assertIn("_Test Study Published John 3:16", prompt)
		self.assertNotIn("_Test Study Draft John", prompt)
		self.refused(self.preached, ai.SERIES_DESCRIPTION)

	def test_handout_blanks_read_only_the_notes(self):
		start = self.run_helper(self.draft, ai.HANDOUT_BLANKS)

		self.assertNotIn(TRANSCRIPT, start.call_args.args[1])
		empty = self.make_sermon("_Test Study Transcript Only", transcript=TRANSCRIPT)
		self.refused(empty, ai.HANDOUT_BLANKS)
		self.refused(self.make_sermon("_Test Study Empty"), ai.SUMMARY)

	def test_no_licensed_verse_text_reaches_a_request(self):
		imported = make_translation(self, "_TSAI", [("JHN", 3, 16, "_Test Licensed Verse Text.")])
		frappe.db.set_value("Church", self.church, "default_bible_translation", imported)
		for purpose in ai.HELPERS:
			sermon = self.published if ai.HELPERS[purpose].published_only else self.draft
			prompt = self.run_helper(sermon, purpose).call_args.args[1]
			self.assertIn("John 3:16", prompt)
			self.assertNotIn("_Test Licensed Verse Text", prompt)

	def test_a_reader_who_cannot_open_the_sermon_or_ai_off_is_refused(self):
		frappe.set_user(WEBSITE_USER)
		self.refused(self.published, ai.SUMMARY, frappe.PermissionError)
		frappe.set_user(STAFF)
		frappe.db.set_single_value(SETTINGS, "enabled", 0)
		self.refused(self.published, ai.SUMMARY, frappe.PermissionError)

	def test_every_helper_names_a_check_that_exists(self):
		for helper in ai.HELPERS.values():
			self.assertTrue(callable(frappe.get_attr(helper.check)), helper.check)

	def test_the_website_never_shows_the_transcript(self):
		fields = published_field_map()["Sermon"]

		self.assertIn("notes", fields)
		self.assertNotIn("transcript", fields)


class TestStudyChecks(RollbackEachTest):
	def test_a_question_that_names_a_passage_not_in_the_bible_is_dropped(self):
		answer = {
			"questions": ["Read John 3:16. What is a gift?", "What does Mark 16:21 say?", 7, " "],
			"references": ["rom 8:28", "Mark 16:21"],
		}
		result = ai.check_questions(answer)

		self.assertEqual(result["questions"], ["Read John 3:16. What is a gift?"])
		self.assertEqual(result["dropped"], ["Mark 16:21"])
		self.assertEqual(
			[passage["reference"] for passage in result["references"]], ["Romans 8:28", "John 3:16"]
		)

	def test_questions_of_the_wrong_shape_cannot_be_used(self):
		for answer in ({}, {"questions": "Why?"}, {"questions": ["Is Mark 16:21 true?"]}):
			with self.assertRaisesRegex(frappe.ValidationError, "The AI answer could not be used."):
				ai.check_questions(answer)

	def test_blanks_are_short_phrases_each_once_without_brackets_or_markup(self):
		answer = {
			"blanks": [
				"grace",
				"[faith] alone",
				"Grace",
				"one two three four five six seven",
				"<b>hope</b>",
				3,
			]
		}
		self.assertEqual(ai.check_blanks(answer), {"blanks": ["grace", "faith alone", "hope"]})
		with self.assertRaises(frappe.ValidationError):
			ai.check_blanks({"blanks": []})
