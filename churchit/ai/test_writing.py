# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Draft with AI: the fields it works on, what each prompt holds, and how each answer is checked."""

from unittest import mock

import frappe

from churchit.ai import runner, writing
from churchit.ai.switch import SETTINGS
from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_address,
	make_function,
	make_translation,
	make_two_churches,
)

MANAGER = "_test_writing_manager@example.com"
STAFF = "_test_writing_staff@example.com"
WEB_EDITOR = "_test_writing_web_editor@example.com"
WEBSITE_USER = "_test_writing_website_user@example.com"
START = "churchit.ai.runner.start"
TEXT_FIELDTYPES = ("Data", "Small Text", "Text Editor")


class WritingTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, _other = make_two_churches()
		for user, roles in (
			(MANAGER, ("Church Manager",)),
			(STAFF, ("Church Staff",)),
			(WEB_EDITOR, ("Church Manager", "Website Manager")),
		):
			ensure_user(user, "Writing", roles)
			set_user_church(user, cls.church)
		ensure_user(WEBSITE_USER, "Writing Website User", ())

	def setUp(self):
		super().setUp()
		frappe.db.set_single_value(SETTINGS, "enabled", 1)

	def draft(self, **kwargs) -> mock.MagicMock:
		"""draft_text with the runner patched; the runner mock, to read what it was given."""
		with mock.patch(START, return_value={"token": "t"}) as start:
			self.assertEqual(writing.draft_text(**kwargs), {"token": "t"})
		return start

	def refused(self, error=frappe.ValidationError, **kwargs) -> None:
		with mock.patch(START) as start, self.assertRaises(error):
			writing.draft_text(**kwargs)
		start.assert_not_called()


class TestPurposes(WritingTestCase):
	def test_each_purpose_names_a_text_field_of_its_form(self):
		for doctype, fields in writing.PURPOSES.items():
			for fieldname, purpose in fields.items():
				df = frappe.get_meta(doctype).get_field(fieldname)
				self.assertIn(df.fieldtype, TEXT_FIELDTYPES, f"{doctype}.{fieldname}")
				if purpose.form:
					tables = [table.options for table in frappe.get_meta(purpose.form).get_table_fields()]
					self.assertIn(doctype, tables)

	def test_every_kind_of_field_names_a_check_that_exists(self):
		kinds = {purpose.kind for fields in writing.PURPOSES.values() for purpose in fields.values()}
		self.assertEqual(set(writing.CHECKS), kinds)
		for path in writing.CHECKS.values():
			self.assertTrue(callable(frappe.get_attr(path)), path)

	def test_the_boot_names_each_field_and_its_actions(self):
		bootinfo = frappe._dict(churchit={})
		writing.extend_bootinfo(bootinfo)
		fields = bootinfo.churchit["ai_writing"]

		self.assertEqual(fields["Church Email"]["message"]["actions"], writing.TEXT_ACTIONS)
		self.assertEqual(fields["Web Page"]["main_section"], {"actions": ("alt_text",), "public_only": True})


class TestDraftText(WritingTestCase):
	def test_a_church_email_starts_a_writer_run_without_church_records(self):
		frappe.set_user(MANAGER)
		start = self.draft(
			doctype="Church Email", fieldname="message", action="write", prompt="Invite all to the picnic"
		)

		prompt = start.call_args.args[1]
		self.assertEqual(start.call_args.args[0], writing.FEATURE)
		self.assertEqual(start.call_args.kwargs["sends"], ())
		self.assertEqual(start.call_args.kwargs["check"], "churchit.ai.writing.check_message")
		self.assertIn("The staff member asks: Invite all to the picnic", prompt)
		self.assertIn("{{ first_name }}", prompt)
		self.assertIn("Markdown", prompt)
		self.assertIn('<data source="facts">\nChurch: _Test Scope A', prompt)

	def test_the_current_text_is_data_and_keeps_its_links(self):
		frappe.set_user(MANAGER)
		text = '<p>Hello <b>{{ first_name }}</b>, see <a href="https://example.org">this</a>.</p><ul><li>One</li></ul>'
		prompt = self.draft(
			doctype="Church Email", fieldname="message", action="shorten", text=text
		).call_args.args[1]

		data = prompt.split('<data source="current text">')[1]
		self.assertIn("**{{ first_name }}**", data)
		self.assertIn("[this](https://example.org)", data)
		self.assertIn("\n- One", data)
		self.assertNotIn("The staff member asks", prompt)

	def test_a_function_description_names_its_title_date_and_place(self):
		address = make_address("_Test Writing Hall").name
		function = make_function(
			"_Test Writing Supper", church=self.church, address=address, meeting_url="https://example.org/x"
		).name
		frappe.set_user(MANAGER)
		prompt = self.draft(
			doctype="Function", fieldname="description", action="write", name=function, prompt="Describe it"
		).call_args.args[1]

		self.assertIn("_Test Writing Supper", prompt)
		self.assertIn(frappe.format("2031-05-01", "Date"), prompt)
		self.assertIn("_Test Writing Hall, Springfield", prompt)
		self.assertNotIn("example.org/x", prompt)

	def test_an_unpublished_function_is_a_church_record_and_a_published_one_is_not(self):
		"""A function that is not published, and its place, may be a meeting in a member's home."""
		address = make_address("_Test Writing Home").name
		function = make_function("_Test Writing Elders", church=self.church, address=address).name
		frappe.set_user(MANAGER)
		draft = {
			"doctype": "Function",
			"fieldname": "description",
			"action": "write",
			"prompt": "Describe it",
		}

		start = self.draft(**draft, name=function)
		self.assertEqual(start.call_args.kwargs["sends"], ("Function", "Address"))
		frappe.db.set_value("Function", function, "publish", 1)
		self.assertEqual(self.draft(**draft, name=function).call_args.kwargs["sends"], ())
		self.assertEqual(self.draft(**draft).call_args.kwargs["sends"], (), "A new form holds typed text")

	def test_a_new_record_takes_only_its_fact_fields_from_the_form(self):
		frappe.set_user(MANAGER)
		values = {"function_name": "_Test Harvest Dinner", "meeting_url": "https://example.org/secret"}
		prompt = self.draft(
			doctype="Function", fieldname="description", action="write", prompt="Describe it", values=values
		).call_args.args[1]

		self.assertIn("_Test Harvest Dinner", prompt)
		self.assertNotIn("secret", prompt)

	def test_bulletin_announcements_name_the_coming_published_functions(self):
		make_function("_Test Writing Youth Night", church=self.church, start_date="2031-05-03", publish=1)
		make_function("_Test Writing Board Meeting", church=self.church, start_date="2031-05-03")
		make_function("_Test Writing Later Night", church=self.church, start_date="2031-07-01", publish=1)
		frappe.set_user(MANAGER)
		values = {"function_name": "_Test Sunday", "function_date": "2031-04-30"}
		prompt = self.draft(
			doctype="Bulletin", fieldname="announcements", action="write", prompt="Announce", values=values
		).call_args.args[1]

		self.assertIn("_Test Writing Youth Night", prompt)
		self.assertNotIn("_Test Writing Board Meeting", prompt)
		self.assertNotIn("_Test Writing Later Night", prompt)

	def test_a_follow_up_text_is_checked_as_a_template_on_its_workflow(self):
		frappe.set_user(MANAGER)
		start = self.draft(doctype="Follow-up Action", fieldname="message", action="write", prompt="Welcome")

		self.assertEqual(start.call_args.kwargs["reference_doctype"], "Follow-up Workflow")
		self.assertEqual(start.call_args.kwargs["check"], "churchit.ai.writing.check_template")
		self.assertIn("{{ step }}", start.call_args.args[1])

	def test_requests_it_cannot_draft_are_refused(self):
		frappe.set_user(MANAGER)
		self.refused(doctype="Person", fieldname="first_name", action="write", prompt="x")
		self.refused(doctype="Church Email", fieldname="message", action="alt_text")
		self.refused(doctype="Church Email", fieldname="message", action="write")
		self.refused(doctype="Church Email", fieldname="message", action="shorten", text=" ")

	def test_a_reader_without_write_and_a_website_user_are_refused(self):
		function = make_function("_Test Writing Read Only", church=self.church).name
		frappe.set_user(STAFF)
		self.refused(
			frappe.PermissionError, doctype="Function", fieldname="description", action="write", name=function
		)
		frappe.set_user(WEBSITE_USER)
		self.refused(frappe.PermissionError, doctype="Church Email", fieldname="message", action="write")

	def test_nothing_runs_while_ai_is_off(self):
		frappe.db.set_single_value(SETTINGS, "enabled", 0)
		frappe.set_user(MANAGER)
		self.refused(
			frappe.PermissionError, doctype="Church Email", fieldname="message", action="write", prompt="x"
		)


class TestAltText(WritingTestCase):
	def make_page(self, **values) -> str:
		key = frappe.generate_hash(length=6)
		page = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": f"_Test Writing Page {key}",
				"route": f"test-writing-page-{key}",
				"content_type": "Rich Text",
				"main_section": '<p>Our choir sang.</p><img src="/files/a.png" alt="Choir"><img src="/files/b.png">',
				**values,
			}
		)
		return page.insert(ignore_permissions=True).name

	def test_alt_text_lists_each_image_without_one_on_a_public_page(self):
		page = self.make_page(published=1)
		frappe.set_user(WEB_EDITOR)
		text = frappe.db.get_value("Web Page", page, "main_section")
		start = self.draft(
			doctype="Web Page", fieldname="main_section", action="alt_text", name=page, text=text
		)

		prompt = start.call_args.args[1]
		self.assertEqual(start.call_args.kwargs["check"], "churchit.ai.writing.check_alt_text")
		self.assertIn('<data source="images">\n1. b.png\n</data>', prompt)
		self.assertNotIn("a.png", prompt)
		self.assertIn("Our choir sang.", prompt)

	def test_alt_text_and_descriptions_wait_until_everyone_can_open_the_page(self):
		frappe.set_user(WEB_EDITOR)
		for page in (self.make_page(published=0), self.make_page(published=1, members_only=1)):
			self.refused(
				doctype="Web Page", fieldname="meta_description", action="write", name=page, prompt="x"
			)
		self.refused(doctype="Web Page", fieldname="meta_description", action="write", prompt="x")


class TestChecks(WritingTestCase):
	def test_listed_references_are_tidied_and_one_not_in_the_bible_is_dropped(self):
		result = writing.check_text({"text": "God is love.", "references": ["jn 3:16", "Mark 16:21", 5]})

		self.assertEqual(result["text"], "God is love.")
		self.assertEqual([passage["reference"] for passage in result["references"]], ["John 3:16"])

	def test_a_sentence_that_names_a_passage_not_in_the_bible_is_dropped(self):
		text = "Read Romans 8:28 today. Mark 16:21 says more.\n\nCall Dan 555-1234 to help."
		result = writing.check_text({"text": text})

		self.assertEqual(result["text"], "Read Romans 8:28 today.\n\nCall Dan 555-1234 to help.")
		self.assertEqual(result["dropped"], ["Mark 16:21"])
		self.assertEqual([passage["reference"] for passage in result["references"]], ["Romans 8:28"])

	def test_verse_text_comes_only_from_the_churchs_free_translation(self):
		verse = [("JHN", 3, 16, "For God so loved _Test Writing.")]
		free = make_translation(self, "_TWF", verse, free=True)
		imported = make_translation(self, "_TWI", verse)
		frappe.set_user(MANAGER)
		for translation, expected in ((free, "16 For God so loved _Test Writing."), (imported, None)):
			frappe.db.set_value("Church", self.church, "default_bible_translation", translation)
			passage = writing.check_text({"text": "See John 3:16."})["references"][0]
			self.assertEqual(passage["text"], expected)
			self.assertEqual(passage["translation"], expected and free)

	def test_a_message_keeps_only_the_placeholders_sending_fills(self):
		self.assertEqual(
			writing.check_message({"text": "Hi {{ first_name }}!"})["text"], "Hi {{ first_name }}!"
		)
		for text in ("Hi {{ frappe.session.user }}", "Bonjour {{ prenom }}", "Now at {{ step }}"):
			with self.assertRaises(frappe.ValidationError):
				writing.check_message({"text": text})
		self.assertEqual(writing.check_template({"text": "Now at {{ step }}"})["text"], "Now at {{ step }}")

	def test_markup_in_an_answer_is_removed(self):
		result = writing.check_text(
			{"text": 'Hi <img src="https://example.org/x.png" onerror="alert(1)">there'}
		)
		self.assertEqual(result["text"], "Hi there")

	def test_an_answer_of_the_wrong_shape_cannot_be_used(self):
		for answer in ([], {}, {"text": 5}, {"text": " "}, {"text": "Mark 16:21 is lovely."}):
			with self.assertRaisesRegex(frappe.ValidationError, "The AI answer could not be used."):
				writing.check_text(answer)

	def test_alt_texts_are_short_single_lines(self):
		result = writing.check_alt_text({"alt_texts": ["A <b>choir</b>\nsinging", "x" * 300, 7]})
		self.assertEqual(result["alt_texts"], ["A choir singing", "x" * writing.ALT_TEXT_LENGTH, "7"])
		with self.assertRaises(frappe.ValidationError):
			writing.check_alt_text({"alt_texts": []})


class TestThroughTheRunner(WritingTestCase):
	"""The runner finds each check by its dotted path and sends the caller its result or its refusal."""

	def complete(self, output: str) -> dict:
		frappe.set_user(MANAGER)
		run = frappe._dict(name="_test-writing-run", status="Completed", output=output)
		job = {
			"token": "w" * 32,
			"feature": writing.FEATURE,
			"user": MANAGER,
			"check": writing.CHECKS["message"],
		}
		frappe.cache.set_value(runner.RUN_KEY + run.name, job, expires_in_sec=60)
		self.addCleanup(frappe.cache.delete_value, runner.ANSWER_KEY + job["token"])
		with mock.patch("churchit.ai.runner.frappe.publish_realtime") as publish:
			runner.complete(run)
		return publish.call_args.args[1]

	def test_a_checked_answer_reaches_the_caller(self):
		message = self.complete('```json\n{"text": "Hi {{ first_name }}, see Mark 16:21."}\n```')
		self.assertNotIn("result", message)

		message = self.complete('{"text": "Hi {{ first_name }}.", "references": ["ps 23"]}')
		self.assertEqual(message["result"]["text"], "Hi {{ first_name }}.")
		self.assertEqual(message["result"]["references"][0]["reference"], "Psalms 23")

	def test_a_placeholder_outside_the_list_is_refused_before_display(self):
		message = self.complete('{"text": "Hi {{ frappe.db }}"}')

		self.assertNotIn("result", message)
		self.assertIn("cannot be filled in for each person", message["error"])
