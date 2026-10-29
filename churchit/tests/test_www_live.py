# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch
from urllib.parse import urlencode

import frappe
from frappe.utils import set_request
from frappe.website.serve import get_response

from churchit.church_website.published_fields import PUBLIC, published_field_map
from churchit.tests.helpers import RollbackEachTest, ensure_root_church, make_two_churches

OWNCAST = "https://stream.example.org/embed/video"


class TestLiveStreamLink(RollbackEachTest):
	def save_link(self, url):
		church = frappe.get_doc("Church", ensure_root_church())
		church.live_stream_url = url
		church.save(ignore_permissions=True)
		return church.live_stream_url

	def test_only_one_https_link_can_be_saved(self):
		for url in ("javascript:alert(1)", "http://stream.example.org/live", "https://a.org/x https://b.org"):
			with self.subTest(url=url), self.assertRaises(frappe.ValidationError):
				self.save_link(url)

		self.assertEqual(self.save_link(f"  {OWNCAST} "), OWNCAST)


class TestLivePage(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.root, cls.branch_a, cls.branch_b):
			frappe.db.set_value("Church", church, {"publish": 1, "live_stream_url": None})

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.local.flags.pop, "redirect_location", None)
		self.addCleanup(setattr, frappe.local, "request", None)
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

	def live(self, church=None):
		frappe.set_user("Guest")
		query = {"church": church} if church else {}
		set_request(method="GET", path="live", query_string=urlencode(query))
		frappe.local.form_dict = frappe._dict(query)
		return get_response("live")

	def assert_player(self, church, src):
		response = self.live(church)
		self.assertEqual(response.status_code, 200)
		self.assertIn(f'<iframe src="{src}"', response.get_data(as_text=True))

	def test_a_branch_uses_its_own_link_else_its_parents(self):
		frappe.db.set_value("Church", self.root, "live_stream_url", OWNCAST)
		frappe.db.set_value("Church", self.branch_a, "live_stream_url", "https://a.example.org/embed/video")

		self.assert_player(self.branch_a, "https://a.example.org/embed/video")
		self.assert_player(self.branch_b, OWNCAST)

	def test_a_youtube_video_or_an_owncast_player_plays_on_the_page(self):
		frappe.db.set_value(
			"Church", self.branch_a, "live_stream_url", "https://www.youtube.com/watch?v=abc123"
		)
		frappe.db.set_value("Church", self.branch_b, "live_stream_url", OWNCAST)

		self.assert_player(self.branch_a, "https://www.youtube.com/embed/abc123")
		self.assert_player(self.branch_b, OWNCAST)

	def test_a_link_with_no_player_redirects_to_it(self):
		url = "https://lets.church/channel/our-church/live"
		frappe.db.set_value("Church", self.branch_a, "live_stream_url", url)

		response = self.live(self.branch_a)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], url)

	def test_no_link_in_the_church_or_its_parents_gives_404(self):
		frappe.db.set_value("Church", self.branch_b, "live_stream_url", OWNCAST)

		self.assertEqual(self.live(self.branch_a).status_code, 404)

	def test_a_link_saved_after_a_404_shows_with_the_website_cache_on(self):
		# force_website_cache would override no_cache, so turn on the cache as production does.
		self.addCleanup(frappe.cache.delete_value, "website_404")
		self.addCleanup(setattr, frappe.local, "no_cache", None)
		with patch.dict(frappe.local.conf, {"developer_mode": 0, "disable_website_cache": 0}):
			self.assertEqual(self.live().status_code, 404)
			frappe.db.set_value("Church", self.root, "live_stream_url", OWNCAST)
			self.assertEqual(self.live().status_code, 200)

	def test_the_link_carries_the_public_badge(self):
		sources = published_field_map().get("Church", {}).get("live_stream_url", [])
		self.assertIn(PUBLIC, [source["access"] for source in sources if source["route"] == "live"])
