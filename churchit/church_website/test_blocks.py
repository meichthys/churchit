# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The church's Web Template blocks and the home page built from them."""

from datetime import datetime, timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, now_datetime

from churchit.church_study.doctype.sermon_handout.sermon_handout import make_handout
from churchit.church_website.blocks import HOME_BLOCKS
from churchit.church_website.pages import sync_page_switches
from churchit.patches.after_install import read_template
from churchit.patches.v1_0 import move_home_page_to_blocks
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_function,
)
from churchit.www.podcast import get_feed_url


def render(block, **values):
	"""The HTML of the church's *block*, a Web Template, with *values*."""
	return frappe.get_doc("Web Template", block).render(values)


def make_sermon(title, **values):
	return frappe.get_doc({"doctype": "Sermon", "title": title, "publish": 1, **values}).insert(
		ignore_permissions=True
	)


class TestChurchBlocks(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.church = ensure_root_church()

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()
		frappe.local.no_cache = 0
		self.addCleanup(setattr, frappe.local, "no_cache", 0)

	def test_every_home_block_renders_and_keeps_its_page_out_of_the_page_cache(self):
		for template, values in HOME_BLOCKS:
			frappe.local.no_cache = 0
			render(template, **values)
			if template != "Church Next Steps":
				self.assertEqual(frappe.local.no_cache, 1, template)

	def test_the_welcome_names_the_church_and_when_it_meets(self):
		make_function(
			"_Test Block Sunday Worship",
			start_date=add_days(getdate(), 2),
			start_time="10:00:00",
			publish=1,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
		)

		html = render("Church Welcome")

		self.assertIn(frappe.db.get_value("Church", self.church, "church_name"), html)
		self.assertIn("_Test Block Sunday Worship", html)
		self.assertIn("Weekly on Sunday at 10:00 AM", html)

	def test_without_a_repeating_function_the_welcome_names_the_next_one(self):
		frappe.db.set_value("Function", {"auto_repeat": 1}, "publish", 0)
		make_function("_Test Block Next Function", start_date=getdate(), start_time="00:00:01", publish=1)

		html = render("Church Welcome")

		self.assertIn("_Test Block Next Function", html)
		self.assertIn("Next on", html)

	def test_the_welcome_points_to_a_stream_that_is_live_now(self):
		frappe.db.set_value("Church", self.church, "live_stream_url", "https://www.youtube.com/watch?v=test")
		started = now_datetime() - timedelta(minutes=5)
		make_function(
			"_Test Block Live Service",
			start_date=started.date(),
			start_time=started.time(),
			end_time=(datetime.combine(started.date(), started.time()) + timedelta(hours=2)).time(),
			streamed=1,
			publish=1,
		)

		html = render("Church Welcome")

		self.assertIn("Live now", html)
		self.assertIn("_Test Block Live Service", html.partition("Live now")[2])

	def test_events_list_published_functions_and_offer_open_sign_ups(self):
		open_one = make_function(
			"_Test Block Open Event", start_date=getdate(), start_time="00:00:01", publish=1
		)
		make_function("_Test Block Draft Event", start_date=getdate(), publish=0)
		make_function("_Test Block Link Only Event", start_date=getdate(), publish=1, is_link_only=1)

		with patch(
			"churchit.church_website.blocks.get_open_functions",
			return_value=[frappe._dict(name=open_one.name)],
		):
			html = render("Church Events", count=50)

		self.assertIn("_Test Block Open Event", html)
		self.assertIn(f'href="/calendar?event={open_one.name}"', html)
		self.assertIn(f'href="/register?function={open_one.name}"', html)
		self.assertNotIn("_Test Block Draft Event", html)
		self.assertNotIn("_Test Block Link Only Event", html)

	def test_sermons_show_the_newest_first_with_the_podcast(self):
		make_sermon(
			"_Test Block Newest Sermon",
			sermon_date="2099-02-01",
			notes="<h3>I. The call</h3><p>Paul urges us by God's [mercy].</p><p>Second paragraph</p>",
		)
		make_sermon("_Test Block Older Sermon", sermon_date="2099-01-01")

		html = render("Church Sermons", count=1)

		self.assertIn("_Test Block Newest Sermon", html)
		self.assertNotIn("_Test Block Older Sermon", html)
		self.assertIn("Paul urges us by God&#39;s mercy.", html)
		self.assertNotIn("Second paragraph", html)
		self.assertIn(f'href="{get_feed_url(self.church)}"', html.replace("&amp;", "&"))

	def test_a_sermon_with_a_handout_shows_none_of_its_notes(self):
		sermon = make_sermon(
			"_Test Block Handout Sermon", sermon_date="2099-03-01", notes="<p>So loved the [world].</p>"
		)
		make_handout(sermon.name)

		html = render("Church Sermons", count=1)

		self.assertIn("_Test Block Handout Sermon", html)
		self.assertNotIn("world", html)

	def test_what_staff_type_is_escaped(self):
		make_sermon("_Test Block <b>Bold</b> Sermon", sermon_date="2099-04-01")

		html = render("Church Sermons", count=1)

		self.assertIn("_Test Block &lt;b&gt;Bold&lt;/b&gt; Sermon", html)
		self.assertNotIn("<b>Bold</b>", html)

	def test_ministries_show_only_the_active_published_ones(self):
		for name, status in (
			("_Test Block Active Ministry", "Active"),
			("_Test Block Ended Ministry", "Inactive"),
		):
			frappe.get_doc(
				{"doctype": "Ministry", "ministry_name": name, "publish": 1, "status": status}
			).insert(ignore_permissions=True)

		html = render("Church Ministries", count=50)

		self.assertIn("_Test Block Active Ministry", html)
		self.assertNotIn("_Test Block Ended Ministry", html)

	def test_next_steps_leave_out_a_switched_off_page(self):
		self.assertIn('href="/find-a-group"', render("Church Next Steps"))
		sync_page_switches()
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": "find-a-group"})[0].enabled = 0
		features.save()

		self.assertNotIn('href="/find-a-group"', render("Church Next Steps"))

	def test_visit_shows_how_to_reach_the_church(self):
		frappe.db.set_value("Church", self.church, {"phone": "_Test 555 0100", "email": "office@example.com"})
		frappe.clear_document_cache("Church", self.church)

		html = render("Church Visit")

		self.assertIn("_Test 555 0100", html)
		self.assertIn('href="mailto:office@example.com"', html)
		self.assertIn('href="/contact"', html)


class TestHomePageBlocks(RollbackEachTest):
	def set_home(self, html):
		if not frappe.db.exists("Web Page", "home"):
			self.skipTest("The site has no home Web Page.")
		page = frappe.get_doc("Web Page", "home")
		page.content_type = "HTML"
		page.page_blocks = []
		page.main_section_html = html
		page.save(ignore_permissions=True)

	def test_the_home_page_as_it_shipped_is_built_from_the_blocks(self):
		self.set_home(read_template("home.html"))

		move_home_page_to_blocks.execute()
		move_home_page_to_blocks.execute()

		page = frappe.get_doc("Web Page", "home")
		self.assertEqual(page.content_type, "Page Builder")
		self.assertEqual(
			[block.web_template for block in page.page_blocks], [name for name, _ in HOME_BLOCKS]
		)
		self.assertEqual(
			page.main_section_html, read_template("home.html"), "the old page stays one switch away"
		)

	def test_a_home_page_the_church_changed_stays_as_it_is(self):
		edited = read_template("home.html").replace("See the calendar", "Our week")
		self.set_home(edited)

		move_home_page_to_blocks.execute()

		page = frappe.get_doc("Web Page", "home")
		self.assertEqual(page.content_type, "HTML")
		self.assertEqual(page.main_section_html, edited)

	def test_a_website_manager_may_read_the_blocks_but_not_change_them(self):
		user = ensure_user("_test_blocks_website_manager@example.com", "Blocks", roles=("Website Manager",))
		frappe.set_user(user)

		self.assertTrue(frappe.has_permission("Web Template", "read", doc=HOME_BLOCKS[0][0]))
		self.assertFalse(frappe.has_permission("Web Template", "write", doc=HOME_BLOCKS[0][0]))
