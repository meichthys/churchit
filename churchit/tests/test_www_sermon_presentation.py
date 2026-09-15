# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure_user, make_person
from churchit.www.sermon_presentation import (
	_build_content_from_selected_fields,
	_parse_display_fields,
	_render_field,
	get_context,
)


class TestSermonPresentationHelpers(FrappeTestCase):
	def test_parse_display_fields_accepts_json_and_legacy_csv(self):
		self.assertEqual(_parse_display_fields(None), [])
		self.assertEqual(_parse_display_fields('{"fieldname": "x"}'), [])
		self.assertEqual(
			_parse_display_fields('[{"fieldname": "title", "is_title": 1}]'),
			[{"fieldname": "title", "is_title": 1}],
		)
		self.assertEqual(
			_parse_display_fields("title, lyrics ,"),
			[
				{"fieldname": "title", "show_label": 1, "is_title": 0},
				{"fieldname": "lyrics", "show_label": 1, "is_title": 0},
			],
		)

	def test_render_field_by_fieldtype(self):
		df = frappe._dict(label="Lyrics", fieldtype="Text Editor")
		self.assertEqual(
			_render_field("<p>Amazing</p>", df, 1), "<p><strong>Lyrics:</strong></p><p>Amazing</p>"
		)
		self.assertEqual(_render_field("<p>Amazing</p>", df, 0), "<p>Amazing</p>")

		image = frappe._dict(label="Cover", fieldtype="Attach Image")
		self.assertIn('<img src="/files/x.png"', _render_field("/files/x.png", image, 0))
		self.assertTrue(_render_field("/files/x.png", image, 1).startswith("<p><strong>Cover:</strong></p>"))

		attach = frappe._dict(label="Sheet", fieldtype="Attach")
		self.assertEqual(
			_render_field("/files/s.pdf", attach, 0),
			'<p><a href="/files/s.pdf" target="_blank">/files/s.pdf</a></p>',
		)

		check = frappe._dict(label="Chorus", fieldtype="Check")
		self.assertEqual(_render_field(1, check, 1), "<p><strong>Chorus:</strong> Yes</p>")
		self.assertEqual(_render_field(0, check, 0), "<p>No</p>")

		self.assertEqual(_render_field("Anon", None, 1), "<p><strong>Field:</strong> Anon</p>")

	def test_build_content_picks_a_title_and_renders_the_rest(self):
		meta = frappe._dict(
			fields=[
				frappe._dict(fieldname="title", label="Title", fieldtype="Data"),
				frappe._dict(fieldname="body", label="Body", fieldtype="Small Text"),
			]
		)
		doc = frappe._dict(title="Hymn 1", body="Verse", missing=None)
		title, content = _build_content_from_selected_fields(
			doc,
			meta,
			[{"fieldname": "title", "is_title": 1}, {"fieldname": "body", "show_label": 0}, "missing"],
		)
		self.assertEqual(title, "Hymn 1")
		self.assertEqual(content, "<p>Verse</p>")


class TestSermonPresentationPage(FrappeTestCase):
	def setUp(self):
		self.preacher = make_person("_Test Preaching", "Pastor")
		self.song = frappe.get_doc({"doctype": "Song", "title": "_Test Hymn", "ccli": "12345"}).insert(
			ignore_permissions=True
		)
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def _sermon(self, title, **values):
		sermon = frappe.get_doc(
			{"doctype": "Sermon", "title": title, "prepared_by": self.preacher.name, **values}
		)
		sermon.append(
			"slides",
			{
				"slide_type": "Song",
				"slide": self.song.name,
				"display_fields": json.dumps(
					[{"fieldname": "title", "is_title": 1}, {"fieldname": "ccli", "show_label": 1}]
				),
				"notes": "Sing softly",
			},
		)
		sermon.append("slides", {"slide_type": "Song", "slide": "SONG-DOES-NOT-EXIST"})
		# A slide whose record was deleted after the sermon was planned.
		sermon.flags.ignore_links = True
		return sermon.insert(ignore_permissions=True)

	def _context(self, sermon):
		frappe.local.form_dict = frappe._dict(name=sermon.name)
		context = frappe._dict()
		get_context(context)
		return context

	def test_missing_name_is_rejected(self):
		with self.assertRaises(ValidationError):
			get_context(frappe._dict())

	def test_unpublished_sermons_need_read_permission(self):
		sermon = self._sermon("_Test Draft Sermon", publish=0)
		frappe.set_user(ensure_user("_test_congregant@example.com", "_Test Congregant", roles=()))
		with self.assertRaises(PermissionError):
			self._context(sermon)

	def test_published_sermon_renders_slides(self):
		sermon = self._sermon("_Test Live Sermon", publish=1)
		frappe.set_user("Guest")
		context = self._context(sermon)

		self.assertEqual(context.sermon_title, "_Test Live Sermon")
		self.assertEqual(context.prepared_by, "_Test Preaching Pastor")
		self.assertTrue(context.no_header)

		first, broken = context.slides
		self.assertEqual(first["title"], "_Test Hymn")
		self.assertEqual(first["content"], "<p><strong>CCLI #:</strong> 12345</p>")
		self.assertEqual(first["notes"], "Sing softly")
		self.assertIn("Could not load Song: SONG-DOES-NOT-EXIST", broken["content"])
