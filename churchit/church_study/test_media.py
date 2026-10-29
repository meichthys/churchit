# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.tests.utils import FrappeTestCase

from churchit.church_study.media import get_embed_url


class TestGetEmbedUrl(FrappeTestCase):
	def assert_embeds(self, cases):
		for url, expected in cases.items():
			with self.subTest(url=url):
				self.assertEqual(get_embed_url(url), expected)

	def test_lets_church_media_plays_in_its_player(self):
		self.assert_embeds(
			{
				"https://lets.church/media/abc": "https://lets.church/embed/media/abc",
				"https://www.lets.church/media/abc-12/": "https://lets.church/embed/media/abc-12",
				"https://lets.church/embed/media/abc": "https://lets.church/embed/media/abc",
			}
		)

	def test_a_lets_church_channel_live_page_has_no_player(self):
		self.assert_embeds(
			{
				"https://lets.church/channel/our-church/live": None,
				"https://lets.church/": None,
			}
		)

	def test_youtube_videos_play_in_the_youtube_player(self):
		player = "https://www.youtube.com/embed/dQw4w9WgXcQ"
		self.assert_embeds(
			{
				"https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42": player,
				"https://youtube.com/watch?v=dQw4w9WgXcQ": player,
				"https://m.youtube.com/watch?v=dQw4w9WgXcQ": player,
				"https://youtu.be/dQw4w9WgXcQ?si=share": player,
				"https://www.youtube.com/live/dQw4w9WgXcQ": player,
				"https://www.youtube.com/embed/dQw4w9WgXcQ": player,
			}
		)

	def test_a_youtube_channel_live_page_plays_the_channels_stream(self):
		player = "https://www.youtube.com/embed/live_stream?channel=UCabc_123-x"
		self.assert_embeds(
			{
				"https://www.youtube.com/channel/UCabc_123-x/live": player,
				player: player,
			}
		)

	def test_youtube_pages_without_a_video_have_no_player(self):
		self.assert_embeds(
			{
				"https://www.youtube.com/@ourchurch/live": None,
				"https://www.youtube.com/watch": None,
				"https://www.youtube.com/watch?v=": None,
				"https://www.youtube.com/embed/live_stream": None,
				"https://www.youtube.com/watch?v=a%22onload%3D": None,
				"https://www.youtube.com/channel/UCabc": None,
				"https://youtu.be/vid\u00e9o": None,
			}
		)

	def test_peertube_videos_play_in_the_instance_player(self):
		self.assert_embeds(
			{
				"https://tube.example.org/w/9c9de5e8-0a1e-484a-b099-e80766180a6d": (
					"https://tube.example.org/videos/embed/9c9de5e8-0a1e-484a-b099-e80766180a6d"
				),
				"https://peertube.example.net:8443/videos/watch/kkGMgK9ZtnKfYAgnEtQxbv": (
					"https://peertube.example.net:8443/videos/embed/kkGMgK9ZtnKfYAgnEtQxbv"
				),
			}
		)

	def test_an_owncast_player_is_kept_as_it_is(self):
		self.assert_embeds(
			{
				"https://stream.example.org/embed/video": "https://stream.example.org/embed/video",
				"https://stream.example.org/embed/video?initiallyMuted=true": (
					"https://stream.example.org/embed/video?initiallyMuted=true"
				),
			}
		)

	def test_every_other_link_has_no_player(self):
		self.assert_embeds(
			{
				None: None,
				"": None,
				"https://example.org/sermons/42": None,
				"https://tube.example.org/w/p/playlist-id": None,
				"https://vimeo.com/123456": None,
				"not a url": None,
			}
		)

	def test_only_https_links_play(self):
		self.assert_embeds(
			{
				"http://lets.church/media/abc": None,
				"http://www.youtube.com/watch?v=dQw4w9WgXcQ": None,
				"http://youtu.be/dQw4w9WgXcQ": None,
				"http://tube.example.org/w/abc": None,
				"http://stream.example.org/embed/video": None,
				"javascript:alert(1)//embed/video": None,
				"https:///embed/video": None,
			}
		)
