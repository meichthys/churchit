# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from urllib.parse import quote, urlencode

import frappe
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website.published_fields import PUBLIC, published_field_map
from churchit.patches.after_install import read_template
from churchit.patches.v1_0 import build_sermon_library
from churchit.tests.helpers import RollbackEachTest, force_single_church, make_two_churches


def make_sermon(title, **values):
	return frappe.get_doc({"doctype": "Sermon", "title": title, "publish": 1, **values}).insert(
		ignore_permissions=True
	)


def serve(path, **query):
	"""The response a Guest gets for *path*."""
	frappe.set_user("Guest")
	set_request(method="GET", path=path, query_string=urlencode(query))
	frappe.local.form_dict = frappe._dict(query)
	try:
		return get_response(path)
	finally:
		frappe.set_user("Administrator")


def serve_sermon(name, **query):
	return serve(f"sermon/{quote(name)}", **query)


class TestSermonPage(RollbackEachTest):
	"""/sermon/<name> shows one published sermon to anyone with the link."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_a_guest_reads_a_published_sermon(self):
		sermon = make_sermon(
			"_Test Page Sermon",
			sermon_date="2031-03-02",
			scripture="John 3:16",
			notes="<p>_Test the main points</p>",
		)

		response = serve_sermon(sermon.name)
		html = response.get_data(as_text=True)
		self.assertEqual(response.status_code, 200)
		self.assertIn("_Test Page Sermon", html)
		self.assertIn("John 3:16", html)
		self.assertIn("_Test the main points", html)
		self.assertIn(frappe.utils.formatdate("2031-03-02"), html)

	def test_an_unpublished_or_missing_sermon_is_not_found(self):
		draft = make_sermon("_Test Draft Page Sermon", publish=0)

		self.assertEqual(serve_sermon(draft.name).status_code, 404)
		self.assertEqual(serve_sermon("_Test No Such Sermon").status_code, 404)
		self.assertEqual(serve("sermon").status_code, 404)

	def test_a_sermon_opens_only_at_its_own_route(self):
		sermon = make_sermon("_Test Route Sermon")

		self.assertEqual(serve_sermon(sermon.name).status_code, 200)
		self.assertEqual(serve("sermon", name=sermon.name).status_code, 404)

	def test_a_known_video_plays_and_any_other_is_a_link(self):
		played = make_sermon("_Test Played Sermon", media_url="https://lets.church/media/abc")
		linked = make_sermon("_Test Linked Sermon", media_url="https://example.org/video/9")

		html = serve_sermon(played.name).get_data(as_text=True)
		self.assertIn('<iframe src="https://lets.church/embed/media/abc"', html)

		html = serve_sermon(linked.name).get_data(as_text=True)
		self.assertNotIn("<iframe", html)
		self.assertIn('href="https://example.org/video/9"', html)

	def test_values_are_escaped(self):
		sermon = make_sermon("_Test Escaped Sermon")
		frappe.db.set_value("Sermon", sermon.name, "scripture", '<img src=x onerror="alert(1)">')

		html = serve_sermon(sermon.name).get_data(as_text=True)
		self.assertNotIn("<img src=x", html)
		self.assertIn("&lt;img src=x", html)

	def test_the_series_shows_only_when_published(self):
		series = frappe.get_doc(
			{"doctype": "Sermon Series", "series_name": "_Test Page Series", "publish": 0}
		).insert(ignore_permissions=True)
		sermon = make_sermon("_Test Series Page Sermon", series=series.name)
		self.assertNotIn("_Test Page Series", serve_sermon(sermon.name).get_data(as_text=True))

		frappe.db.set_value("Sermon Series", series.name, "publish", 1)
		self.assertIn("_Test Page Series", serve_sermon(sermon.name).get_data(as_text=True))

	def test_the_page_fields_carry_the_public_badge(self):
		published = published_field_map()
		for doctype, fieldname in (
			("Sermon", "sermon_date"),
			("Sermon", "scripture"),
			("Sermon", "media_url"),
			("Sermon", "notes"),
		):
			with self.subTest(field=f"{doctype}.{fieldname}"):
				sources = published[doctype][fieldname]
				self.assertIn(("sermon", PUBLIC), {(s["route"], s["access"]) for s in sources})
		self.assertNotIn("notes", published.get("Sermon Presentation", {}))


class TestSermonPageChurches(RollbackEachTest):
	"""The link opens from any branch, but not for a church that is not published."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.church, "publish", 1)
		frappe.db.set_value("Church", cls.other_church, "publish", 0)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_a_sermon_of_an_unpublished_church_is_not_found(self):
		hidden = make_sermon("_Test Closed Church Sermon", church=self.other_church)
		shown = make_sermon("_Test Open Church Sermon", church=self.church)

		self.assertEqual(serve_sermon(hidden.name).status_code, 404)
		self.assertEqual(serve_sermon(shown.name, church=self.other_church).status_code, 200)

	def test_a_shared_sermon_opens_from_any_church(self):
		shared = make_sermon("_Test Shared Page Sermon", church=self.other_church, is_shared=1)

		self.assertEqual(frappe.db.get_value("Sermon", shared.name, "church"), "")
		self.assertEqual(serve_sermon(shared.name, church=self.church).status_code, 200)


class TestSermonsPage(RollbackEachTest):
	"""The shipped /sermons Web Page: newest first, searchable, linked to each sermon."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		if not frappe.db.exists("Web Page", "sermons"):
			frappe.get_doc(
				{
					"doctype": "Web Page",
					"title": "Sermons",
					"route": "sermons",
					"published": 1,
					"content_type": "HTML",
					"dynamic_template": 1,
				}
			).insert(ignore_permissions=True)

	def setUp(self):
		super().setUp()
		frappe.db.set_value(
			"Web Page", "sermons", {"main_section_html": read_template("sermons.html"), "published": 1}
		)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def serve_sermons(self, **query):
		# Any query string keeps the page out of the shared page cache between tests.
		return serve("sermons", fresh="1", **query).get_data(as_text=True)

	def test_a_search_lists_only_matching_title_or_scripture(self):
		by_title = make_sermon("_Test John Sermon Title")
		by_scripture = make_sermon("_Test Search Scripture Sermon", scripture="John 1:1")
		other = make_sermon("_Test Search Other Sermon", scripture="Psalms 23")

		html = self.serve_sermons(q="John")
		self.assertIn(by_title.title, html)
		self.assertIn(by_scripture.title, html)
		self.assertNotIn(other.title, html)
		self.assertIn(f'href="/sermon/{quote(by_title.name)}"', html)
		self.assertIn('value="John"', html)

	def test_the_search_text_is_escaped(self):
		html = self.serve_sermons(q='"><script>alert(1)</script>')
		self.assertNotIn("<script>alert(1)", html)
		self.assertIn("&lt;script&gt;", html)

	def test_sermons_are_sorted_newest_first(self):
		older = make_sermon("_Test Sorted Older Sermon", sermon_date="2030-01-05")
		newer = make_sermon("_Test Sorted Newer Sermon", sermon_date="2031-01-05")

		html = self.serve_sermons(q="_Test Sorted")
		self.assertLess(html.index(newer.title), html.index(older.title))

	def test_a_series_shows_its_public_image(self):
		series = frappe.get_doc(
			{
				"doctype": "Sermon Series",
				"series_name": "_Test Image Series",
				"publish": 1,
				"image": "/files/_test_series.png",
			}
		).insert(ignore_permissions=True)
		make_sermon("_Test Image Series Sermon", series=series.name)

		html = self.serve_sermons()
		self.assertIn('src="/files/_test_series.png"', html)
		self.assertIn("Sermon Series", published_field_map())
		self.assertIn("image", published_field_map()["Sermon Series"])

	def test_a_series_hides_a_private_image(self):
		series = frappe.get_doc(
			{
				"doctype": "Sermon Series",
				"series_name": "_Test Private Image Series",
				"publish": 1,
				"image": "/private/files/_test_series.png",
			}
		).insert(ignore_permissions=True)
		make_sermon("_Test Private Image Sermon", series=series.name)

		self.assertNotIn("/private/files/_test_series.png", self.serve_sermons())


class TestSermonsPageChurches(RollbackEachTest):
	"""A branch's search keeps its church."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.church, cls.other_church):
			frappe.db.set_value("Church", church, "publish", 1)

	def setUp(self):
		super().setUp()
		frappe.db.set_value("Web Page", "sermons", "main_section_html", read_template("sermons.html"))

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_the_search_stays_in_the_selected_church(self):
		mine = make_sermon("_Test Branch Search Mine", church=self.church)
		theirs = make_sermon("_Test Branch Search Theirs", church=self.other_church)

		html = serve("sermons", church=self.church, q="_Test Branch Search").get_data(as_text=True)
		self.assertIn(mine.title, html)
		self.assertNotIn(theirs.title, html)
		self.assertIn(f'<input type="hidden" name="church" value="{self.church}">', html)


class TestSermonLibraryPatch(RollbackEachTest):
	"""The patch rewrites only the sermons page this app shipped, and dates old sermons."""

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Web Page", "sermons"):
			self.skipTest("The site has no sermons Web Page.")

	def set_page(self, html):
		frappe.db.set_value("Web Page", "sermons", "main_section_html", html)

	def page(self):
		return frappe.db.get_value("Web Page", "sermons", "main_section_html")

	def test_the_shipped_page_is_rewritten(self):
		self.set_page(build_sermon_library.SHIPPED_SERMONS)

		build_sermon_library.execute()
		build_sermon_library.execute()

		self.assertEqual(self.page(), read_template("sermons.html"))

	def test_a_page_that_differs_only_by_whitespace_is_rewritten(self):
		self.set_page(build_sermon_library.SHIPPED_SERMONS.replace("<div", "\n\n  <div", 1))

		build_sermon_library.execute()

		self.assertEqual(self.page(), read_template("sermons.html"))

	def test_an_edited_page_is_left_alone(self):
		edited = build_sermon_library.SHIPPED_SERMONS.replace("Please check back soon.", "Soon!")
		self.set_page(edited)

		build_sermon_library.execute()

		self.assertEqual(self.page(), edited)

	def test_old_sermons_take_the_date_of_their_first_presentation(self):
		sermon = make_sermon(
			"_Test Backfilled Sermon",
			presentation_history=[{"date": "2031-03-01"}, {"date": "2030-01-05"}],
		)
		frappe.db.set_value("Sermon", sermon.name, "sermon_date", None, update_modified=False)
		modified = frappe.db.get_value("Sermon", sermon.name, "modified")

		build_sermon_library.execute()

		self.assertEqual(str(frappe.db.get_value("Sermon", sermon.name, "sermon_date")), "2030-01-05")
		self.assertEqual(frappe.db.get_value("Sermon", sermon.name, "modified"), modified)
