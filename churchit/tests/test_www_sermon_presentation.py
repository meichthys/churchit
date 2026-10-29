# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.church_website.published_fields import published_field_map
from churchit.tests.helpers import ensure_user, make_person, make_translation
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
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.preacher = make_person("_Test Preaching", "Pastor")
		cls.song = frappe.get_doc({"doctype": "Song", "title": "_Test Hymn", "ccli": "12345"}).insert(
			ignore_permissions=True
		)

	def setUp(self):
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
		frappe.set_user(ensure_user("_test_sermon_staff@example.com", "_Test Staff", roles=("Church Staff",)))
		context = self._context(sermon)

		self.assertEqual(context.sermon_title, "_Test Live Sermon")
		self.assertEqual(context.prepared_by, "_Test Preaching Pastor")
		self.assertTrue(context.no_header)

		first, deleted = context.slides
		self.assertEqual(first["title"], "_Test Hymn")
		self.assertEqual(first["content"], "<p><strong>CCLI #:</strong> 12345</p>")
		self.assertEqual(first["notes"], "Sing softly")
		self.assertEqual(deleted["content"], "<p>This slide is not public</p>")
		self.assertNotIn("SONG-DOES-NOT-EXIST", str(deleted))

	def test_guest_sees_no_person_slide(self):
		person = make_person("_Test Slide", "Member")
		belief = frappe.get_doc(
			{"doctype": "Belief", "title": "_Test Grace", "belief_statement": "Saved by grace", "publish": 1}
		).insert(ignore_permissions=True)
		missionary = frappe.get_doc(
			{"doctype": "Missionary", "title": "_Test Sent One", "publish": 1, "support_amount": 4321}
		).insert(ignore_permissions=True)
		every_field = json.dumps(
			[
				{"fieldname": f, "show_label": 1}
				for f in ("first_name", "email", "belief_statement", "support_amount")
			]
		)
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Slides Sermon",
				"publish": 1,
				"slides": [
					{"slide_type": "Person", "slide": person.name, "display_fields": every_field},
					{"slide_type": "Belief", "slide": belief.name, "display_fields": every_field},
					{"slide_type": "Missionary", "slide": missionary.name, "display_fields": every_field},
					{"slide_type": "Missionary", "slide": missionary.name},
				],
			}
		).insert(ignore_permissions=True)

		frappe.set_user("Guest")
		person_slide, belief_slide, missionary_slide, titled = self._context(sermon).slides
		self.assertEqual(person_slide["content"], "<p>This slide is not public</p>")
		self.assertNotIn("_Test Slide", str(person_slide))
		self.assertNotIn(person.name, str(person_slide))
		self.assertIn("Saved by grace", belief_slide["content"])
		self.assertNotIn("4321", missionary_slide["content"])
		self.assertEqual((titled["title"], titled["content"]), ("_Test Sent One", ""))

		frappe.set_user("Administrator")
		missionary.db_set("sensitive", 1)
		frappe.set_user("Guest")
		self.assertEqual(self._context(sermon).slides[3]["content"], "<p>This slide is not public</p>")

	def test_a_scripture_slide_shows_its_verses_or_only_its_reference(self):
		free = make_translation(
			self, "_TSP", [("PSA", 23, 1, "The LORD is my shepherd;\nI shall not want.")], free=True
		)
		imported = make_translation(self, "_TSQ", [("PSA", 23, 1, "The LORD is my shepherd.")])
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Scripture Sermon",
				"publish": 1,
				"slides": [
					{"scripture": "ps 23:1", "translation": free},
					{"scripture": "Psalms 23:1", "translation": imported},
				],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(sermon.slides[0].scripture, "Psalms 23:1")

		frappe.set_user("Guest")
		readable, withheld = self._context(sermon).slides
		self.assertEqual(readable["title"], f"Psalms 23:1 ({free})")
		self.assertIn("<sup>1</sup> The LORD is my shepherd;<br>I shall not want.", readable["content"])
		self.assertEqual((withheld["title"], withheld["content"]), ("Psalms 23:1", ""))

	def test_a_slide_shows_no_field_the_viewer_cannot_read(self):
		person = make_person("_Test Private", "Slide")
		frappe.db.set_value(
			"Person", person.name, {"medical_notes": "_SECRET MEDICAL", "team_calendar_key": "_SECRETKEY"}
		)
		private_fields = json.dumps(
			[{"fieldname": f} for f in ("first_name", "medical_notes", "team_calendar_key")]
		)
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Private Fields Sermon",
				"publish": 1,
				"slides": [{"slide_type": "Person", "slide": person.name, "display_fields": private_fields}],
			}
		).insert(ignore_permissions=True)

		for email, role, hidden in (
			("_test_sermon_staff@example.com", "Church Staff", ("_SECRET MEDICAL", "_SECRETKEY")),
			("_test_sermon_manager@example.com", "Church Manager", ("_SECRETKEY",)),
		):
			frappe.set_user(ensure_user(email, role, roles=(role,)))
			content = self._context(sermon).slides[0]["content"]
			self.assertIn("_Test Private", content, role)
			for value in hidden:
				self.assertNotIn(value, content, role)

	def test_the_badges_name_only_the_public_slide_fields(self):
		published = published_field_map()

		def routes(doctype, fieldname):
			return {source["route"] for source in published.get(doctype, {}).get(fieldname, [])}

		self.assertIn("sermon-presentation", routes("Missionary", "title"))
		self.assertIn("sermon-presentation", routes("Belief", "belief_statement"))
		self.assertNotIn("sermon-presentation", routes("Missionary", "support_amount"))
		self.assertNotIn("sermon-presentation", routes("Missionary", "notes"))
