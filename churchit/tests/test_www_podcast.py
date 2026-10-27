# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from xml.etree import ElementTree

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import CallbackManager, get_datetime, getdate, set_request
from frappe.website.serve import get_response

from churchit.church_website.context import update_website_context
from churchit.church_website.published_fields import published_field_map
from churchit.tests.helpers import RollbackEachTest, force_single_church, make_two_churches
from churchit.www.podcast import get_public_file_sizes

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def make_sermon(title, audio=None, private=False, presentations=(), **values):
	"""A sermon whose audio and presentation recordings are remote files, so nothing moves on disk."""
	values.setdefault("publish", 1)
	sermon = frappe.get_doc(
		{
			"doctype": "Sermon",
			"title": title,
			"presentation_history": [
				{"date": date, "audio_recording": url} for date, url, _ in presentations
			],
			**values,
		}
	).insert(ignore_permissions=True)
	if audio:
		attach(sermon, audio, private)
		frappe.db.set_value("Sermon", sermon.name, "audio_recording", audio)
	for _date, url, is_private in presentations:
		attach(sermon, url, is_private)
	return sermon


def attach(sermon, url, is_private):
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": url.rpartition("/")[2],
			"file_url": url,
			"file_size": 4096,
			"is_private": int(is_private),
			"attached_to_doctype": "Sermon",
			"attached_to_name": sermon.name,
			"attached_to_field": "audio_recording",
		}
	).insert(ignore_permissions=True)
	# A File save can flip privacy only for local files; set the stored flag as the test asks.
	frappe.db.set_value("File", {"file_url": url}, "is_private", int(is_private))


def serve_feed(church=None):
	query = urlencode({"church": church}) if church else ""
	set_request(method="GET", path="podcast.xml", query_string=query)
	frappe.set_user("Guest")
	frappe.local.form_dict = frappe._dict(church=church) if church else frappe._dict()
	try:
		response = get_response("podcast.xml")
	finally:
		frappe.set_user("Administrator")
	return response, ElementTree.fromstring(response.get_data(as_text=True))


def items_by_title(feed):
	return {item.findtext("title"): item for item in feed.iter("item")}


class TestPodcastFeed(RollbackEachTest):
	def setUp(self):
		super().setUp()
		force_single_church()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_the_feed_is_rss_2_with_the_itunes_tags(self):
		sermon = make_sermon(
			"_Test Podcast Grace", "https://example.com/_test_grace.mp3", sermon_date="2030-05-05"
		)

		response, feed = serve_feed()
		self.assertEqual(response.status_code, 200)
		self.assertIn("xml", response.mimetype)
		self.assertEqual(feed.tag, "rss")
		self.assertEqual(feed.get("version"), "2.0")

		channel = feed.find("channel")
		self.assertTrue(channel.findtext("language"))
		self.assertTrue(channel.find(f"{ITUNES}image").get("href").startswith("http"))
		self.assertEqual(channel.find(f"{ITUNES}category").get("text"), "Religion & Spirituality")
		self.assertEqual(channel.findtext(f"{ITUNES}explicit"), "false")

		item = items_by_title(feed)["_Test Podcast Grace"]
		enclosure = item.find("enclosure")
		self.assertEqual(enclosure.get("url"), "https://example.com/_test_grace.mp3")
		self.assertEqual(enclosure.get("length"), "4096")
		self.assertEqual(enclosure.get("type"), "audio/mpeg")
		self.assertEqual(parsedate_to_datetime(item.findtext("pubDate")).date(), getdate("2030-05-05"))
		self.assertEqual(item.find("guid").get("isPermaLink"), "false")
		self.assertIn(get_datetime(sermon.creation).isoformat(), item.findtext("guid"))
		self.assertTrue(item.findtext("link").endswith(f"/sermon/{sermon.name}"))

	def test_only_published_sermons_with_public_audio_are_listed(self):
		make_sermon("_Test Podcast Listed", "https://example.com/_test_listed.mp3")
		make_sermon("_Test Podcast Draft", "https://example.com/_test_draft.mp3", publish=0)
		make_sermon("_Test Podcast Private", "https://example.com/_test_private.mp3", private=True)
		make_sermon("_Test Podcast Silent")

		titles = items_by_title(serve_feed()[1])
		self.assertIn("_Test Podcast Listed", titles)
		self.assertNotIn("_Test Podcast Draft", titles)
		self.assertNotIn("_Test Podcast Private", titles)
		self.assertNotIn("_Test Podcast Silent", titles)

	def test_no_recording_matches_a_file_with_no_url(self):
		self.assertEqual(get_public_file_sizes([None, ""]), {})

	def test_a_presentation_recording_stands_in_for_missing_audio(self):
		make_sermon(
			"_Test Podcast Preached Twice",
			presentations=[
				("2030-01-01", "https://example.com/_test_first.mp3", False),
				("2030-02-01", "https://example.com/_test_second.mp3", False),
				("2030-03-01", "https://example.com/_test_third.mp3", True),
			],
		)

		item = items_by_title(serve_feed()[1])["_Test Podcast Preached Twice"]
		self.assertEqual(item.find("enclosure").get("url"), "https://example.com/_test_second.mp3")
		self.assertEqual(parsedate_to_datetime(item.findtext("pubDate")).date(), getdate("2030-02-01"))

	def test_text_reads_as_written_and_markup_cannot_break_the_feed(self):
		title = "_Test Podcast Faith & Works {next}"
		# Frappe stores "&" in a Data field as "&amp;", and an escaped tag unescapes to markup.
		notes = "<p>&lt;/channel&gt; James 2 &amp; <b>works</b></p><p>Line one<br>Line two</p>"
		make_sermon(title, "https://example.com/_test_works.mp3", notes=notes)

		item = items_by_title(serve_feed()[1])[title]
		# A reader parses the description as HTML, so the typed tag must stay an entity.
		self.assertEqual(
			item.findtext("description"), "&lt;/channel&gt; James 2 &amp; works\nLine one\nLine two"
		)

	def test_the_sermons_page_points_feed_readers_at_the_podcast(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.local.path = "sermons"
		context = frappe._dict()
		update_website_context(context)
		self.assertIn('<link rel="alternate" type="application/rss+xml"', context.head_html)
		self.assertIn('href="/podcast.xml"', context.head_html)

		frappe.local.path = "about"
		context = frappe._dict()
		update_website_context(context)
		self.assertNotIn("application/rss+xml", context.head_html)

	def test_the_sermons_page_head_carries_the_feed_link(self):
		self.addCleanup(setattr, frappe.local, "request", None)
		frappe.local.form_dict = frappe._dict()
		set_request(method="GET", path="sermons")
		html = get_response("sermons").get_data(as_text=True)
		head = html.partition("</head>")[0]
		self.assertIn('type="application/rss+xml"', head)

	def test_the_feed_badges_what_it_shows_and_not_staff_notes(self):
		published = published_field_map()
		self.assertIn("podcast", [source["route"] for source in published["Sermon"]["audio_recording"]])
		self.assertIn("audio_recording", published["Sermon Presentation"])
		self.assertIn("date", published["Sermon Presentation"])
		self.assertNotIn("notes", published["Sermon Presentation"])


class TestPodcastFeedOfOneChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_a, "publish", 1)
		frappe.db.set_value("Church", cls.branch_b, "publish", 1)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_a_church_feed_lists_its_own_and_shared_sermons_only(self):
		make_sermon("_Test Podcast Of A", "https://example.com/_test_a.mp3", church=self.branch_a)
		make_sermon("_Test Podcast Of B", "https://example.com/_test_b.mp3", church=self.branch_b)
		make_sermon(
			"_Test Podcast Shared By B",
			"https://example.com/_test_shared.mp3",
			church=self.branch_b,
			is_shared=1,
		)

		_response, feed = serve_feed(self.branch_a)
		titles = items_by_title(feed)
		self.assertIn("_Test Podcast Of A", titles)
		self.assertIn("_Test Podcast Shared By B", titles)
		self.assertNotIn("_Test Podcast Of B", titles)

		channel = feed.find("channel")
		self.assertEqual(
			channel.findtext("title"), frappe.db.get_value("Church", self.branch_a, "church_name")
		)
		self_link = channel.find("{http://www.w3.org/2005/Atom}link").get("href")
		self.assertTrue(self_link.endswith("/podcast.xml?" + urlencode({"church": self.branch_a})), self_link)

	def test_the_head_link_names_the_selected_church(self):
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		frappe.local.path = "sermons"
		frappe.local.form_dict = frappe._dict(church=self.branch_a)
		context = frappe._dict()
		update_website_context(context)
		self.assertIn(f'href="/podcast.xml?{urlencode({"church": self.branch_a})}"', context.head_html)


class TestRecordingPrivacyFollowsPublish(FrappeTestCase):
	"""A presentation's recording is public exactly while its sermon is published."""

	def setUp(self):
		# A move queues a move back for a rollback; this test deletes its file instead.
		self.addCleanup(setattr, frappe.db, "after_rollback", frappe.db.after_rollback)
		frappe.db.after_rollback = CallbackManager()
		self.sermon = frappe.get_doc({"doctype": "Sermon", "title": "_Test Podcast Privacy"})
		self.sermon.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Sermon", self.sermon.name, force=True)
		self.file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"_test_{frappe.generate_hash(length=8)}.mp3",
				"content": frappe.generate_hash(),
				"is_private": 1,
				"attached_to_doctype": "Sermon",
				"attached_to_name": self.sermon.name,
				"attached_to_field": "audio_recording",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(lambda: frappe.delete_doc("File", self.file.name, force=True))

	def test_publishing_moves_a_presentation_recording_to_public_files(self):
		self.sermon.append(
			"presentation_history", {"date": "2030-01-01", "audio_recording": self.file.file_url}
		)
		self.sermon.publish = 1
		self.sermon.save(ignore_permissions=True)

		self.file.reload()
		self.assertFalse(self.file.is_private)
		self.assertTrue(self.file.file_url.startswith("/files/"))
		row = self.sermon.presentation_history[0]
		self.assertEqual(
			frappe.db.get_value("Sermon Presentation", row.name, "audio_recording"), self.file.file_url
		)
		self.assertIsNone(frappe.db.get_value("Sermon", self.sermon.name, "audio_recording"))
		self.assertEqual(
			frappe.db.get_value("Sermon", self.sermon.name, "modified"), get_datetime(self.sermon.modified)
		)

		# The open form saves again without a reload.
		self.sermon.publish = 0
		self.sermon.save(ignore_permissions=True)

		self.file.reload()
		self.assertTrue(self.file.is_private)
		self.assertEqual(
			frappe.db.get_value("Sermon Presentation", row.name, "audio_recording"), self.file.file_url
		)
