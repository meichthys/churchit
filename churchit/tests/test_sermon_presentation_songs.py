# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError
from frappe.tests.utils import FrappeTestCase

from churchit.church_foundations.church_access import set_user_church
from churchit.church_scope import default_church
from churchit.tests.helpers import (
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_two_churches,
	set_multi_church,
)
from churchit.www.sermon_presentation import get_context

NOT_PUBLIC = "<p>This slide is not public</p>"


def make_song(title, slides, **values):
	return frappe.get_doc(
		{
			"doctype": "Song",
			"title": title,
			"slides": [{"content": f"<p>{text}</p>"} for text in slides],
			**values,
		}
	).insert(ignore_permissions=True)


def make_sermon(title, songs, church, **values):
	sermon = frappe.get_doc(
		{
			"doctype": "Sermon",
			"title": title,
			"publish": 1,
			"slides": [{"slide_type": "Song", "slide": song} for song in songs],
			**values,
		}
	).insert(ignore_permissions=True)
	sermon.db_set("church", church)
	return sermon


def presentation(**form):
	frappe.local.form_dict = frappe._dict(form)
	context = frappe._dict()
	get_context(context)
	return context


class TestSermonPresentationSongs(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root = ensure_root_church()
		frappe.db.set_value("Church", cls.root, "ccli_license_number", "_A5ROOT")
		cls.staff = ensure_user("_test_a5_staff@example.com", "_Test A5 Staff", roles=("Church Staff",))
		cls.nobody = ensure_user("_test_a5_nobody@example.com", "_Test A5 Nobody", roles=())
		cls.licensed = make_song(
			"_Test A5 Licensed Song",
			["Verse one", "Chorus", "Verse two"],
			copyright="2001 _A5 Music",
			ccli="_A5CCLI",
		)
		cls.hymn = make_song("_Test A5 Hymn", ["Hymn verse", "Hymn refrain"], public_domain=1)

	def setUp(self):
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def test_a_song_row_shows_each_slide_and_then_its_copyright(self):
		sermon = make_sermon("_Test A5 Song Sermon", [self.licensed.name], self.root)
		frappe.set_user(self.staff)
		slides = presentation(name=sermon.name).slides

		self.assertEqual(len(slides), 4)
		self.assertEqual(
			[slide["content"] for slide in slides[:3]], [slide.content for slide in self.licensed.slides]
		)
		credits = slides[3]
		self.assertEqual(credits["title"], "_Test A5 Licensed Song")
		self.assertIn("2001 _A5 Music", credits["content"])
		self.assertIn("CCLI Song # _A5CCLI, CCLI License # _A5ROOT", credits["content"])

	def test_a_guest_sees_only_public_domain_songs(self):
		sermon = make_sermon("_Test A5 Guest Sermon", [self.hymn.name, self.licensed.name], self.root)
		frappe.set_user("Guest")
		slides = presentation(name=sermon.name).slides

		self.assertEqual(len(slides), 4)
		self.assertEqual(
			[slide["content"] for slide in slides[:2]], ["<p>Hymn verse</p>", "<p>Hymn refrain</p>"]
		)
		self.assertEqual(slides[2]["title"], "_Test A5 Hymn")
		self.assertEqual((slides[3]["title"], slides[3]["content"]), ("", NOT_PUBLIC))
		self.assertNotIn("_Test A5 Licensed Song", str(slides))
		self.assertNotIn("Verse one", str(slides))

	def test_a_guest_never_gets_a_private_background(self):
		hymn = make_song("_Test A5 Background Hymn", ["Private sky", "Public sky"], public_domain=1)
		hymn.slides[0].db_set("background_image", "/private/files/_a5_secret.png")
		hymn.slides[1].db_set("background_image", "/files/_a5_sky.png")
		sermon = make_sermon("_Test A5 Background Sermon", [hymn.name], self.root)
		frappe.set_user("Guest")
		slides = presentation(name=sermon.name).slides

		self.assertEqual(slides[0]["content"], "<p>Private sky</p>")
		self.assertIsNone(slides[0]["background_image"])
		self.assertEqual(slides[1]["background_image"], "/files/_a5_sky.png")
		self.assertNotIn("_a5_secret", str(slides))

	def test_a_single_church_site_shows_the_root_churchs_license(self):
		self.addCleanup(
			set_multi_church, frappe.db.get_single_value("Church Features", "enable_multi_church")
		)
		force_single_church()
		sermon = make_sermon("_Test A5 Single Church Sermon", [self.licensed.name], None)
		frappe.set_user(self.staff)

		self.assertIn("CCLI License # _A5ROOT", presentation(name=sermon.name).slides[-1]["content"])

	def test_a_song_slide_shows_its_background_image(self):
		song = make_song("_Test A5 Background Song", ["Words"])
		song.slides[0].db_set("background_image", "/files/_a5_sky.png")
		frappe.set_user(self.staff)
		slides = presentation(song=song.name).slides
		self.assertEqual(slides[0]["background_image"], "/files/_a5_sky.png")

	def test_present_a_song_without_a_sermon(self):
		frappe.set_user(self.staff)
		context = presentation(song=self.licensed.name)

		self.assertEqual(context.sermon_title, "_Test A5 Licensed Song")
		self.assertEqual(len(context.slides), 4)
		self.assertIn(
			f"CCLI License # {frappe.db.get_value('Church', default_church(), 'ccli_license_number')}",
			context.slides[-1]["content"],
		)

	def test_present_a_song_needs_song_read(self):
		for user in ("Guest", self.nobody):
			frappe.set_user(user)
			with self.assertRaises(PermissionError, msg=user):
				presentation(song=self.hymn.name)


class TestSongLicenseOfEachChurch(FrappeTestCase):
	"""A shared sermon shows the license of the viewer's church, any other the license of its own church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_a, "ccli_license_number", "_A5LICENSEA")
		frappe.db.set_value("Church", branch_b, "ccli_license_number", "_A5LICENSEB")
		cls.manager_b = ensure_user(
			"_test_a5_manager_b@example.com", "_Test A5 Manager", roles=("Church Manager",)
		)
		set_user_church(cls.manager_b, branch_b)
		cls.song = make_song(
			"_Test A5 Shared Song", ["Words"], ccli="_A5SHARED", church=cls.branch_a, is_shared=1
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def test_the_license_follows_the_sermon_or_the_viewer(self):
		own = make_sermon("_Test A5 Branch Sermon", [self.song.name], self.branch_a)
		shared = make_sermon("_Test A5 Shared Sermon", [self.song.name], self.branch_a)
		# A shared record stores no church.
		shared.db_set({"is_shared": 1, "church": ""})

		frappe.set_user(self.manager_b)
		self.assertIn("CCLI License # _A5LICENSEA", presentation(name=own.name).slides[-1]["content"])
		self.assertIn("CCLI License # _A5LICENSEB", presentation(name=shared.name).slides[-1]["content"])
		self.assertIn("CCLI License # _A5LICENSEB", presentation(song=self.song.name).slides[-1]["content"])
