# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days

from churchit.church_communications.doctype.bulletin.bulletin import (
	SECTION_FIELDS,
	get_defaults,
	missionary_of_the_week,
	supported_missionaries,
)
from churchit.church_foundations.doctype.church.church import get_church
from churchit.church_study.doctype.sermon_handout.sermon_handout import make_handout
from churchit.tests.helpers import ensure, make_function, make_person, make_translation

FUNCTION_DATE = "2031-05-04"


class TestBulletin(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.settings = frappe.get_doc("Bulletin Settings")
		cls.function = make_function("_Test Bulletin Service", start_date=FUNCTION_DATE)

	def make_bulletin(self, **values):
		bulletin = frappe.get_doc({"doctype": "Bulletin", "function": self.function.name, **values})
		return bulletin.insert(ignore_permissions=True)

	def make_missionary(self, title, **values):
		return frappe.get_doc({"doctype": "Missionary", "title": title, **values}).insert(
			ignore_permissions=True
		)

	def make_prayer_request(self, title, **values):
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": title,
				"type": ensure("Prayer Request Type", {"type": "_Test Prayer Type"}),
				**values,
			}
		).insert(ignore_permissions=True)

	def test_title_names_the_function_and_date(self):
		bulletin = self.make_bulletin()
		self.assertEqual(bulletin.function_name, "_Test Bulletin Service")
		self.assertEqual(str(bulletin.function_date), FUNCTION_DATE)
		self.assertIn("_Test Bulletin Service", bulletin.title)
		self.assertIn("2031", bulletin.title)

	def test_defaults_come_from_settings_and_the_function(self):
		self.settings.show_ministries = 0
		self.settings.show_birthdays = 1
		self.settings.save(ignore_permissions=True)
		open_request = self.make_prayer_request("_Test Open Request")
		private_request = self.make_prayer_request("_Test Private Request", is_private=1)
		answered_request = self.make_prayer_request("_Test Answered Request", status="Answered")
		expired_request = self.make_prayer_request("_Test Expired Request", end_date="2020-01-01 00:00:00")

		defaults = get_defaults(self.function.name)

		self.assertEqual(defaults["show_ministries"], 0)
		self.assertEqual(defaults["show_birthdays"], 1)
		self.assertEqual(set(defaults) - {"prayer_requests"}, {*SECTION_FIELDS, "missionary"})
		picked = {row["prayer_request"] for row in defaults["prayer_requests"]}
		self.assertIn(open_request.name, picked)
		self.assertNotIn(private_request.name, picked)
		self.assertNotIn(answered_request.name, picked)
		self.assertNotIn(expired_request.name, picked)
		self.assertEqual(
			next(row for row in defaults["prayer_requests"] if row["prayer_request"] == open_request.name)[
				"title"
			],
			"_Test Open Request",
		)

	def test_missionary_rotation_skips_sensitive_and_ended_support(self):
		supported = self.make_missionary("_Test Supported Missionary")
		sensitive = self.make_missionary("_Test Sensitive Missionary", sensitive=1)
		former = self.make_missionary("_Test Former Missionary", support_end_date="2020-01-01")

		names = supported_missionaries(FUNCTION_DATE)
		self.assertIn(supported.name, names)
		self.assertNotIn(sensitive.name, names)
		self.assertNotIn(former.name, names)

		with_sensitive = supported_missionaries(FUNCTION_DATE, include_sensitive=True)
		self.assertIn(sensitive.name, with_sensitive)
		self.assertNotIn(former.name, with_sensitive)

	def test_missionary_rotation_changes_weekly_and_wraps(self):
		self.make_missionary("_Test Rotation Missionary A")
		self.make_missionary("_Test Rotation Missionary B")
		names = supported_missionaries(FUNCTION_DATE)
		weeks = len(names)

		picks = [missionary_of_the_week(add_days(FUNCTION_DATE, 7 * week)) for week in range(weeks)]

		first = names.index(picks[0])
		self.assertEqual(picks, names[first:] + names[:first])
		self.assertEqual(missionary_of_the_week(add_days(FUNCTION_DATE, 7 * weeks)), picks[0])
		self.assertEqual(
			missionary_of_the_week(FUNCTION_DATE), missionary_of_the_week(add_days(FUNCTION_DATE, 3))
		)

	def test_sensitive_missionary_is_refused_unless_settings_allow(self):
		sensitive = self.make_missionary("_Test Refused Missionary", sensitive=1)
		self.settings.include_sensitive_missionaries = 0
		self.settings.save(ignore_permissions=True)

		self.assertRaises(frappe.ValidationError, self.make_bulletin, missionary=sensitive.name)

		self.settings.include_sensitive_missionaries = 1
		self.settings.save(ignore_permissions=True)
		self.assertEqual(self.make_bulletin(missionary=sensitive.name).missionary, sensitive.name)

	def test_private_prayer_request_is_refused(self):
		private_request = self.make_prayer_request("_Test Private Bulletin Request", is_private=1)
		self.assertRaises(
			frappe.ValidationError,
			self.make_bulletin,
			prayer_requests=[{"prayer_request": private_request.name}],
		)

	def test_church_roles_list_current_holders_in_settings_order(self):
		pastor = ensure("Position Type", {"position": "_Test Pastor"})
		deacon = ensure("Position Type", {"position": "_Test Deacon"})
		make_person("Zed", "_Test Bulletin", positions=[{"position": pastor, "start_date": "2020-01-01"}])
		make_person("Amy", "_Test Bulletin", positions=[{"position": pastor, "start_date": "2020-01-01"}])
		make_person(
			"Old",
			"_Test Bulletin",
			positions=[{"position": deacon, "start_date": "2020-01-01", "end_date": "2021-01-01"}],
		)
		make_person("New", "_Test Bulletin", positions=[{"position": deacon, "start_date": "2040-01-01"}])
		self.settings.set("roles", [{"position_type": deacon}, {"position_type": pastor}])
		self.settings.save(ignore_permissions=True)

		roles = self.make_bulletin().church_roles

		self.assertEqual(
			[(role.role, role.people) for role in roles],
			[(pastor, ["Amy _Test Bulletin", "Zed _Test Bulletin"])],
		)

	def test_upcoming_functions_stay_inside_the_window(self):
		self.settings.upcoming_functions_days = 7
		self.settings.save(ignore_permissions=True)
		make_function("_Test Midweek Function", start_date=add_days(FUNCTION_DATE, 3), start_time="19:00:00")
		make_function("_Test Far Function", start_date=add_days(FUNCTION_DATE, 8))
		make_function("_Test Past Function", start_date=add_days(FUNCTION_DATE, -1))

		upcoming = self.make_bulletin().upcoming_functions

		names = [function.name for function in upcoming]
		self.assertIn("_Test Midweek Function", names)
		self.assertNotIn("_Test Far Function", names)
		self.assertNotIn("_Test Past Function", names)
		self.assertNotIn("_Test Bulletin Service", names)
		midweek = next(function for function in upcoming if function.name == "_Test Midweek Function")
		self.assertEqual(midweek.time, "7:00 PM")
		self.assertEqual(midweek.day, "Wed, May 7")

	def test_order_of_worship_uses_item_titles_and_times(self):
		song = ensure("Song", {"title": "_Test Bulletin Hymn"})
		self.function.set(
			"schedule",
			[
				{"start": f"{FUNCTION_DATE} 10:00:00", "description": "Call to worship"},
				{
					"start": f"{FUNCTION_DATE} 10:05:00",
					"item_type": "Song",
					"item": song,
					"description": "Verses 1-3",
				},
			],
		)
		self.function.save(ignore_permissions=True)

		rows = self.make_bulletin().order_of_worship

		self.assertEqual(
			[(row.time, row.title, row.detail) for row in rows],
			[
				("10:00 AM", "Call to worship", None),
				("10:05 AM", "_Test Bulletin Hymn", "Verses 1-3"),
			],
		)

	def test_sermon_handouts_come_from_sermons_on_the_schedule(self):
		preacher = make_person("Paul", "_Test Preacher")
		sermon = frappe.get_doc(
			{
				"doctype": "Sermon",
				"title": "_Test Bulletin Sermon",
				"prepared_by": preacher.name,
				"notes": "<p>[Grace]</p>",
			}
		).insert(ignore_permissions=True)
		handout = make_handout(sermon.name)
		self.function.set("schedule", [{"item_type": "Sermon", "item": sermon.name}])
		self.function.save(ignore_permissions=True)

		handouts = self.make_bulletin().sermon_handouts

		self.assertEqual(len(handouts), 1)
		self.assertEqual(handouts[0].handout.name, handout)
		self.assertEqual(handouts[0].preacher, "Paul _Test Preacher")
		self.assertIn('class="blank"', handouts[0].handout.rendered_content)

	def test_church_verse_comes_from_the_church_record(self):
		translation = self.use_translation([("JHN", 3, 16, "Whoever believes in him shall not perish.")])
		church = frappe.get_doc("Church", get_church().name)
		church.church_verse = "jn 3:16"
		church.save(ignore_permissions=True)
		self.addCleanup(frappe.db.set_value, "Church", church.name, "church_verse", None)
		self.assertEqual(church.church_verse, "John 3:16")
		self.settings.show_church_verse = 1
		self.settings.save(ignore_permissions=True)

		bulletin = self.make_bulletin()

		self.assertEqual(bulletin.show_church_verse, 1)
		self.assertEqual(bulletin.church_verse.reference, f"John 3:16 ({translation})")
		self.assertIn("Whoever believes", frappe.get_print("Bulletin", bulletin.name, "Bulletin"))

		bulletin.show_church_verse = 0
		bulletin.save(ignore_permissions=True)
		self.assertNotIn("Whoever believes", frappe.get_print("Bulletin", bulletin.name, "Bulletin"))

	def test_church_image_comes_from_the_church_record(self):
		church = frappe.get_doc("Church", get_church().name)
		church.image = "/files/_test_church_logo.png"
		church.save(ignore_permissions=True)
		self.addCleanup(frappe.db.set_value, "Church", church.name, "image", None)
		self.settings.show_church_image = 1
		self.settings.save(ignore_permissions=True)

		bulletin = self.make_bulletin()

		self.assertEqual(bulletin.show_church_image, 1)
		self.assertEqual(bulletin.church_image, "/files/_test_church_logo.png")
		self.assertIn('class="church-image"', frappe.get_print("Bulletin", bulletin.name, "Bulletin"))

		bulletin.show_church_image = 0
		bulletin.save(ignore_permissions=True)
		self.assertNotIn('class="church-image"', frappe.get_print("Bulletin", bulletin.name, "Bulletin"))

	def test_contact_information_prefers_the_churchs_own_phone_and_email(self):
		church = frappe.get_doc("Church", get_church().name)
		church.phone = "555-0199"
		church.email = "office@branch.example.com"
		church.save(ignore_permissions=True)

		contact = self.make_bulletin().contact_information

		self.assertEqual((contact.phone, contact.email), ("555-0199", "office@branch.example.com"))

	def test_verse_of_the_week_is_printed_with_its_text_when_there_is_one(self):
		translation = self.use_translation([("JHN", 3, 16, "For God so loved the world.")])
		bulletin = self.make_bulletin(verse="jn 3:16")

		self.assertEqual(bulletin.verse, "John 3:16")
		self.assertEqual(
			bulletin.verse_of_the_week,
			{"reference": f"John 3:16 ({translation})", "text": "16 For God so loved the world."},
		)
		frappe.db.set_value("Bible Translation", translation, "status", "No Text")
		self.assertEqual(bulletin.verse_of_the_week, {"reference": "John 3:16", "text": None})

	def use_translation(self, rows):
		"""Make the bulletin church read a test translation holding *rows*."""
		translation = make_translation(self, "_TBV", rows)
		church = get_church().name
		original = frappe.db.get_value("Church", church, "default_bible_translation")
		frappe.db.set_value("Church", church, "default_bible_translation", translation)
		self.addCleanup(frappe.db.set_value, "Church", church, "default_bible_translation", original)
		return translation

	def test_print_format_renders_every_section(self):
		self.settings.set("roles", [{"position_type": ensure("Position Type", {"position": "_Test Pastor"})}])
		self.settings.save(ignore_permissions=True)
		bulletin = self.make_bulletin(welcome="<p>Welcome friends</p>", announcements="<p>Potluck Sunday</p>")

		html = frappe.get_print("Bulletin", bulletin.name, "Bulletin")

		self.assertIn("orientation: Landscape", html)
		self.assertIn("_Test Bulletin Service", html)
		self.assertIn("Welcome friends", html)
		self.assertIn("Potluck Sunday", html)
		self.assertIn("Order of Worship", html)

	def test_published_bulletins_are_readable_by_portal_users(self):
		bulletin = self.make_bulletin()
		self.assertFalse(bulletin.has_website_permission("read", "member@example.com"))

		bulletin.publish = 1
		bulletin.save(ignore_permissions=True)
		self.assertTrue(bulletin.has_website_permission("read", "member@example.com"))
		self.assertFalse(bulletin.has_website_permission("read", "Guest"))
		self.assertFalse(bulletin.has_website_permission("write", "member@example.com"))
