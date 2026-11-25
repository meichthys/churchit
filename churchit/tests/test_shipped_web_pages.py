# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The shipped home, sermons, ministries, missions and beliefs Web Pages, the footer links and their patches."""

from unittest.mock import patch

import frappe
from frappe.utils import getdate

from churchit.church_study.doctype.sermon_handout.sermon_handout import make_handout
from churchit.church_website.pages import is_link_off, sync_page_switches
from churchit.patches import after_install
from churchit.patches.after_install import read_template
from churchit.patches.v1_0 import (
	add_live_sermon_list,
	add_website_footer_links,
	fix_shipped_missions_and_home_pages,
	fix_shipped_page_dates_and_sermon_pages,
	fix_shipped_page_queries_and_headings,
	fix_shipped_sermon_excerpt_and_missions_map,
	list_sermons_one_a_row,
	show_footer_on_login_page,
	tidy_shipped_website_pages,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_root_church,
	force_single_church,
	make_address,
	make_function,
	make_person,
)


def make_sermon(title, **values):
	return frappe.get_doc({"doctype": "Sermon", "title": title, "publish": 1, **values}).insert(
		ignore_permissions=True
	)


def render(page, **context):
	return frappe.render_template(read_template(f"{page}.html"), context)


def count_queries(page):
	"""The queries one render of *page* runs, once a first render has filled the caches."""
	render(page)
	database = frappe.db.__class__
	with patch.object(database, "sql", autospec=True, side_effect=database.sql) as counted:
		render(page)
	return counted.call_count


def missionary_card(html, title):
	return html.partition(title)[2].partition('class="col-md-4')[0]


def shipped_template(name):
	"""*name*'s template as the patches before the sermon list left it."""
	if name == "sermons":
		return list_sermons_one_a_row.SHIPPED_SERMONS
	return read_template(f"{name}.html")


def unfix(html, *patches):
	"""*html* with the groups of *patches* undone, latest patch first, as each page shipped before them."""
	for groups in patches:
		for group in reversed(groups):
			for old, new in reversed(group):
				assert new in html, new
				html = html.replace(new, old)
	return html


class TestShippedPages(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def switch_off(self, *routes):
		sync_page_switches()
		features = frappe.get_single("Church Features")
		for route in routes:
			features.get("website_pages", {"route": route})[0].enabled = 0
		features.save()

	def test_the_home_page_shows_the_newest_sermon_not_the_last_edited(self):
		make_sermon("_Test Shipped Newest Sermon", sermon_date="2099-01-05")
		make_sermon("_Test Shipped Older Sermon", sermon_date="2098-01-05")

		html = render("home")
		self.assertIn("_Test Shipped Newest Sermon", html)
		self.assertNotIn("_Test Shipped Older Sermon", html)

	def test_the_upcoming_panel_does_not_repeat_the_next_gathering(self):
		make_function("_Test Shipped First Gathering", start_date=getdate(), start_time="00:00:01", publish=1)
		make_function(
			"_Test Shipped Second Gathering", start_date=getdate(), start_time="00:00:02", publish=1
		)

		html = render("home")
		self.assertEqual(html.count("_Test Shipped First Gathering"), 1)
		self.assertIn("_Test Shipped Second Gathering", html.partition('class="home-schedule"')[2])

	def test_the_home_page_hides_links_to_a_switched_off_calendar_or_contact_page(self):
		make_function(
			"_Test Shipped Linked Gathering", start_date=getdate(), start_time="00:00:01", publish=1
		)
		make_function("_Test Shipped Later Gathering", start_date=getdate(), start_time="00:00:02", publish=1)
		html = render("home")
		self.assertEqual(html.count('href="/calendar"'), 3)
		self.assertIn('href="/contact"', html)

		self.switch_off("calendar", "contact")
		html = render("home")
		self.assertNotIn('href="/calendar"', html)
		self.assertNotIn('href="/contact"', html)

	def test_before_setup_the_home_page_shows_no_login_details(self):
		html = render("home", get_church=lambda: None)
		self.assertIn("This website is being set up", html)
		self.assertIn('href="/login"', html)
		self.assertNotIn("Administrator", html)
		self.assertNotIn("Password", html)

	def test_a_sermon_card_shows_only_an_escaped_summary_of_its_notes(self):
		make_sermon(
			"_Test Shipped Summary Sermon",
			sermon_date="2099-03-02",
			notes="<p>_Test the opening &lt;script&gt;</p><h3>Points</h3><ol><li>_Test point one</li></ol>",
		)

		frappe.local.form_dict = frappe._dict(q="_Test Shipped Summary")
		html = render("sermons")
		self.assertIn("_Test the opening &lt;script&gt;", html)
		self.assertNotIn("_Test the opening <script>", html)
		self.assertNotIn("_Test point one", html)
		self.assertIn("Monday, March 2, 2099", html)

	def test_a_sermon_with_a_handout_shows_none_of_its_notes(self):
		sermon = make_sermon(
			"_Test Shipped Handout Sermon", sermon_date="2099-02-01", notes="<p>God so loved the [world].</p>"
		)
		make_handout(sermon.name)

		home = render("home")
		self.assertIn("_Test Shipped Handout Sermon", home)
		self.assertNotIn("[world]", home)

		frappe.local.form_dict = frappe._dict(q="_Test Shipped Handout")
		html = render("sermons")
		self.assertIn("_Test Shipped Handout Sermon", html)
		self.assertNotIn("[world]", html)

	def test_ministries_read_their_start_date_in_the_long_form(self):
		frappe.get_doc(
			{
				"doctype": "Ministry",
				"ministry_name": "_Test Shipped Ministry",
				"publish": 1,
				"status": "Active",
				"start_date": "2021-09-12",
			}
		).insert(ignore_permissions=True)

		self.assertIn("Est. Sunday, September 12, 2021", render("ministries"))

	def test_a_missionary_photo_has_alt_text(self):
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Shipped Missionary",
				"publish": 1,
				"photo": "/files/_test_shipped_missionary.png",
			}
		).insert(ignore_permissions=True)

		self.assertIn(
			'<img src="/files/_test_shipped_missionary.png" alt="_Test Shipped Missionary">',
			render("missions"),
		)

	def test_a_sermon_summary_skips_the_outline_heading_and_the_handout_blanks(self):
		make_sermon(
			"_Test Shipped Outline Sermon",
			sermon_date="2099-04-02",
			notes="<h3>I. The call</h3><p>Paul urges us by God's [mercy].</p><p>Second paragraph</p>",
		)

		home = render("home")
		frappe.local.form_dict = frappe._dict(q="_Test Shipped Outline")
		for html in (home, render("sermons")):
			self.assertIn("Paul urges us by God&#39;s mercy.", html)
			self.assertNotIn("The callPaul", html)
			self.assertNotIn("[mercy]", html)
			self.assertNotIn("Second paragraph", html)

	def test_the_missions_page_shows_the_map_only_with_a_listed_missionary(self):
		frappe.db.set_value("Missionary", {"publish": 1}, "publish", 0)
		html = render("missions")
		self.assertNotIn('id="missions-map"', html)
		self.assertIn("Our missions information is being updated.", html)

		frappe.get_doc(
			{"doctype": "Missionary", "title": "_Test Shipped Map Missionary", "publish": 1}
		).insert(ignore_permissions=True)
		self.assertIn('id="missions-map"', render("missions"))

	def test_the_list_pages_run_no_more_queries_for_more_rows(self):
		preacher = make_person("_Test Shipped", "Preacher").name
		agency = frappe.get_doc(
			{"doctype": "Missionary Agency", "agency_name": "_Test Shipped Agency"}
		).insert(ignore_permissions=True)

		def add_rows(number):
			for row in range(number):
				# Dated after every other sermon, so each is on the first page of 12.
				make_sermon(
					f"_Test Shipped Count Sermon {number} {row}",
					prepared_by=preacher,
					sermon_date="2099-12-31",
				)
				frappe.get_doc(
					{
						"doctype": "Missionary",
						"title": f"_Test Shipped Count Missionary {number} {row}",
						"publish": 1,
						"agency": agency.name,
						"country": "Kenya",
					}
				).insert(ignore_permissions=True)
				frappe.get_doc(
					{
						"doctype": "Ministry",
						"ministry_name": f"_Test Shipped Count Ministry {number} {row}",
						"publish": 1,
						"status": "Active",
					}
				).insert(ignore_permissions=True)
				frappe.get_doc(
					{
						"doctype": "Belief",
						"title": f"_Test Shipped Count Belief {number} {row}",
						"belief_statement": "_Test",
						"publish": 1,
					}
				).insert(ignore_permissions=True)

		pages = ("sermons", "missions", "ministries", "beliefs")
		add_rows(1)
		few = {page: count_queries(page) for page in pages}
		add_rows(3)
		many = {page: count_queries(page) for page in pages}

		self.assertEqual(many, few)
		self.assertIn("_Test Shipped Preacher", render("sermons"))
		card = (
			render("missions")
			.partition("_Test Shipped Count Missionary 1 0")[2]
			.partition('class="col-md-4')[0]
		)
		self.assertIn("_Test Shipped Agency", card)
		self.assertIn("flagcdn.com/w40/ke.png", card)

	def test_the_newest_sermon_of_a_series_opens_the_rest_of_it(self):
		series = frappe.get_doc(
			{"doctype": "Sermon Series", "series_name": "_Test Shipped Series", "publish": 1}
		).insert(ignore_permissions=True)
		for day in (1, 2, 3):
			make_sermon(
				f"_Test Shipped Series Sermon {day}", series=series.name, sermon_date=f"2099-05-0{day}"
			)
		make_sermon("_Test Shipped Single Sermon", sermon_date="2099-05-04")

		frappe.local.form_dict = frappe._dict(q="_Test Shipped S")
		html = render("sermons")

		rows = html.split('<li class="sermon-entry">')[1:]
		self.assertEqual(len(rows), 2, "one row for the single sermon, one for the series")
		self.assertIn("_Test Shipped Single Sermon", rows[0])
		newest, _, rest = rows[1].partition("<details")
		self.assertIn("_Test Shipped Series Sermon 3", newest)
		self.assertIn("2 more sermons in _Test Shipped Series", rest)
		self.assertIn("_Test Shipped Series Sermon 2", rest)
		self.assertIn("_Test Shipped Series Sermon 1", rest)

	def test_the_missions_page_leaves_out_an_inactive_missionary(self):
		for title, status in (
			("_Test Shipped Active Missionary", "Active"),
			("_Test Shipped Gone Missionary", "Inactive"),
		):
			frappe.get_doc({"doctype": "Missionary", "title": title, "publish": 1, "status": status}).insert(
				ignore_permissions=True
			)

		html = render("missions")
		self.assertIn("_Test Shipped Active Missionary", html)
		self.assertNotIn("_Test Shipped Gone Missionary", html)

	def test_a_missionary_card_names_the_country_and_has_a_body_only_with_a_photo(self):
		for title, photo in (
			("_Test Shipped Photo Missionary", "/files/_test_shipped_photo.png"),
			("_Test Shipped Plain Missionary", None),
		):
			frappe.get_doc(
				{"doctype": "Missionary", "title": title, "publish": 1, "photo": photo, "country": "Kenya"}
			).insert(ignore_permissions=True)

		html = render("missions")
		with_photo = missionary_card(html, "_Test Shipped Photo Missionary")
		plain = missionary_card(html, "_Test Shipped Plain Missionary")

		self.assertIn('class="card-body"', with_photo)
		self.assertNotIn('class="card-body"', plain)
		for card in (with_photo, plain):
			self.assertIn('<img src="https://flagcdn.com/w40/ke.png" alt="" style="width: 2em">', card)
			self.assertIn("Kenya", card.partition('alt=""')[2])
			self.assertNotIn("mailto:", card)

	def test_a_missionary_card_escapes_the_title_and_website_that_staff_type(self):
		frappe.get_doc(
			{
				"doctype": "Missionary",
				"title": "_Test Shipped <b>Bold</b> Missionary",
				"publish": 1,
				"website": 'https://example.com/" onmouseover="alert(1)',
			}
		).insert(ignore_permissions=True)

		card = missionary_card(render("missions"), "_Test Shipped &lt;b&gt;Bold&lt;/b&gt; Missionary")

		self.assertNotIn("<b>Bold</b>", render("missions"))
		self.assertIn('href="https://example.com/&#34; onmouseover=&#34;alert(1)"', card)

	def test_the_next_gathering_is_a_named_section_and_the_emoji_are_hidden(self):
		make_function("_Test Shipped Named Gathering", start_date=getdate(), start_time="00:00:01", publish=1)
		make_function("_Test Shipped After Gathering", start_date=getdate(), start_time="00:00:02", publish=1)
		make_sermon("_Test Shipped Message Sermon", sermon_date="2099-06-07")
		church = frappe._dict(
			frappe.get_cached_doc("Church", ensure_root_church()).as_dict(),
			address=make_address("_Test Shipped Home Address").name,
		)

		html = render("home", get_church=lambda: church)

		self.assertNotIn("<aside", html)
		self.assertIn('<section class="card home-aside" aria-labelledby="home-next-gathering">', html)
		self.assertIn('<h2 class="home-aside-title" id="home-next-gathering">', html)
		for emoji in ("📍", "🎧", "📅"):
			self.assertEqual(html.count(emoji), 1, emoji)
			self.assertIn(f'<span aria-hidden="true">{emoji}</span>', html)

	def test_sermons_come_twelve_to_a_page_with_older_and_newer_links(self):
		for day in range(1, 15):
			make_sermon(f"_Test Paged Sermon {day:02}", sermon_date=f"2099-07-{day:02}")
		frappe.local.form_dict = frappe._dict(q="_Test Paged Sermon")

		first = render("sermons")
		frappe.local.form_dict.page = "2"
		second = render("sermons")

		self.assertIn("_Test Paged Sermon 14", first)
		self.assertIn("_Test Paged Sermon 03", first)
		self.assertNotIn("_Test Paged Sermon 02", first)
		self.assertIn('href="/sermons?q=_Test+Paged+Sermon&page=2"', first)
		self.assertNotIn("Newer sermons", first)
		self.assertIn("_Test Paged Sermon 02", second)
		self.assertIn("_Test Paged Sermon 01", second)
		self.assertNotIn("_Test Paged Sermon 03", second)
		self.assertIn('href="/sermons?q=_Test+Paged+Sermon">&larr; Newer sermons', second)
		self.assertNotIn("Older sermons", second)

	def test_a_page_after_the_last_sermon_links_back_to_the_newest(self):
		make_sermon("_Test Last Page Sermon", sermon_date="2099-08-01")
		frappe.local.form_dict = frappe._dict(q="_Test Last Page", page="5")

		html = render("sermons")

		self.assertIn("There are no more sermons.", html)
		self.assertIn('href="/sermons?q=_Test+Last+Page"', html)
		self.assertNotIn("No sermons have been published yet", html)

	def test_a_series_opens_every_sermon_of_the_series_from_any_page(self):
		series = frappe.get_doc(
			{"doctype": "Sermon Series", "series_name": "_Test Paged Series", "publish": 1}
		).insert(ignore_permissions=True)
		for day in range(1, 14):
			make_sermon(
				f"_Test Paged Series Sermon {day:02}", series=series.name, sermon_date=f"2099-09-{day:02}"
			)
		frappe.local.form_dict = frappe._dict(q="_Test Paged Series Sermon")

		self.assertIn("12 more sermons in _Test Paged Series", render("sermons"))

	def test_the_home_page_leaves_out_a_recurring_template(self):
		template = make_function(
			"_Test Shipped Template", start_date=getdate(), start_time="00:00:01", publish=1
		)
		frappe.db.set_value("Function", template.name, "auto_repeat", 1)
		make_function("_Test Shipped Occurrence", start_date=getdate(), start_time="00:00:02", publish=1)

		html = render("home")

		self.assertNotIn("_Test Shipped Template", html)
		self.assertIn("_Test Shipped Occurrence", html)

	def test_the_next_gathering_reads_its_date_in_the_long_form(self):
		day = getdate()
		make_function("_Test Shipped Long Date", start_date=day, start_time="00:00:01", publish=1)
		make_function("_Test Shipped Short Date", start_date=day, start_time="00:00:02", publish=1)

		html = render("home")

		self.assertIn(frappe.utils.formatdate(day, "EEEE, MMMM d, yyyy"), html)
		schedule = html.partition('class="home-schedule"')[2]
		self.assertIn(f'<span class="home-schedule-date">{frappe.utils.formatdate(day)}</span>', schedule)

	def test_a_missionary_card_is_as_tall_as_its_own_text(self):
		frappe.get_doc(
			{"doctype": "Missionary", "title": "_Test Shipped Short Missionary", "publish": 1}
		).insert(ignore_permissions=True)
		html = render("missions")
		self.assertIn('<div class="card">', html)
		self.assertNotIn("h-100", html)


class TestTidyShippedWebPagesPatch(RollbackEachTest):
	"""The patch turns each page as it shipped into the current template, and keeps a church's edits."""

	def set_page(self, name, html):
		if not frappe.db.exists("Web Page", name):
			self.skipTest(f"The site has no {name} Web Page.")
		frappe.db.set_value("Web Page", name, "main_section_html", html)

	def page(self, name):
		return frappe.db.get_value("Web Page", name, "main_section_html")

	def test_each_page_as_it_shipped_becomes_the_current_template(self):
		later = (
			fix_shipped_page_dates_and_sermon_pages.GROUPS,
			fix_shipped_missions_and_home_pages.GROUPS,
			fix_shipped_page_queries_and_headings.GROUPS,
			fix_shipped_sermon_excerpt_and_missions_map.GROUPS,
		)
		names = set(tidy_shipped_website_pages.FIXES) | set(fix_shipped_page_queries_and_headings.GROUPS)
		for name in names:
			shipped = unfix(shipped_template(name), *(groups.get(name, ()) for groups in later))
			self.set_page(name, unfix(shipped, (tidy_shipped_website_pages.FIXES.get(name, ()),)))

		for _run in range(2):
			tidy_shipped_website_pages.execute()
			fix_shipped_sermon_excerpt_and_missions_map.execute()
			fix_shipped_page_queries_and_headings.execute()
			fix_shipped_missions_and_home_pages.execute()
			fix_shipped_page_dates_and_sermon_pages.execute()

		for name in names:
			self.assertEqual(self.page(name), shipped_template(name), name)

	def test_the_sermon_list_becomes_a_live_part_once(self):
		current = shipped_template("sermons")
		self.set_page("sermons", unfix(current, add_live_sermon_list.GROUPS["sermons"]))

		add_live_sermon_list.execute()
		add_live_sermon_list.execute()

		self.assertEqual(self.page("sermons"), current)

	def test_a_page_with_part_of_its_shipped_text_changes_only_the_groups_it_still_has(self):
		current = shipped_template("sermons")
		shipped = unfix(current, fix_shipped_page_queries_and_headings.GROUPS["sermons"])
		edited = shipped.replace("&larr; Back to series", "&larr; All sermons in the series")
		self.set_page("sermons", edited)

		fix_shipped_page_queries_and_headings.execute()

		page = self.page("sermons")
		self.assertIn("preachers.get(sermon.prepared_by)", page)
		self.assertIn('<a href="#" class="series-sermon-link"', page)
		self.assertIn("All sermons in the series", page)

	def test_an_edited_missions_page_keeps_its_own_text(self):
		edited = '<div class="missions-map-card">Our map</div>\n<p>Our own missions</p>'
		self.set_page("missions", edited)

		fix_shipped_sermon_excerpt_and_missions_map.execute()

		self.assertEqual(self.page("missions"), edited)

	def test_an_edited_missions_or_home_part_keeps_its_own_text(self):
		groups = fix_shipped_missions_and_home_pages.GROUPS
		missions = unfix(read_template("missions.html"), groups["missions"])
		home = unfix(read_template("home.html"), groups["home"])
		self.set_page(
			"missions", missions.replace('<p class="card-text">', '<p class="card-text our-photo">')
		)
		self.set_page("home", home.replace("🎧", "🎵"))

		fix_shipped_missions_and_home_pages.execute()

		missions, home = self.page("missions"), self.page("home")
		self.assertIn('<p class="card-text our-photo">', missions)
		self.assertIn(
			'            <div class="card-body">\n                {% if missionary.photo %}', missions
		)
		self.assertIn("{{ missionary.country | e }}", missions)
		self.assertNotIn("mailto:", missions)
		self.assertIn('🎵 {{ _("Latest message") }}', home)
		self.assertIn("📍 {{ address_line }}", home)
		self.assertIn('aria-labelledby="home-next-gathering"', home)

	def test_a_rewritten_missions_or_home_page_stays_as_it_is(self):
		self.set_page("missions", "<p>Our own missions</p>")
		self.set_page("home", '<aside>Our own welcome</aside> 📅 {{ _("Upcoming") }}')

		fix_shipped_missions_and_home_pages.execute()

		self.assertEqual(self.page("missions"), "<p>Our own missions</p>")
		self.assertEqual(self.page("home"), '<aside>Our own welcome</aside> 📅 {{ _("Upcoming") }}')

	def test_an_edited_page_keeps_its_own_text(self):
		edited = '<p>Our own hero</p>\n{%- set sermons = frappe.get_all("Sermon", order_by="title") -%}'
		self.set_page("home", edited)
		self.set_page("ministries", "<p>Our own ministries</p>")

		tidy_shipped_website_pages.execute()
		fix_shipped_page_queries_and_headings.execute()

		self.assertEqual(self.page("home"), edited)
		self.assertEqual(self.page("ministries"), "<p>Our own ministries</p>")

	def test_an_edited_dated_or_paged_part_keeps_its_own_text(self):
		groups = fix_shipped_page_dates_and_sermon_pages.GROUPS
		sermons = unfix(shipped_template("sermons"), groups["sermons"])
		home = unfix(read_template("home.html"), groups["home"])
		self.set_page(
			"sermons", sermons.replace('order_by="sermon_date desc, modified desc"', 'order_by="title"')
		)
		self.set_page("home", home.replace('"EEE, d MMM"', '"d MMM"'))

		fix_shipped_page_dates_and_sermon_pages.execute()

		sermons, home = self.page("sermons"), self.page("home")
		self.assertIn('formatdate(sermon.sermon_date, "EEEE, MMMM d, yyyy")', sermons)
		self.assertNotIn("page_length", sermons)
		self.assertIn('order_by="title"', sermons)
		self.assertIn('format_date(event.start_date, "d MMM")', home)
		self.assertIn('format_date(next_up.start_date, "EEEE, MMMM d, yyyy")', home)
		self.assertIn("auto_repeat=0", home)


class TestSermonListPatch(RollbackEachTest):
	"""The patch turns the shipped sermon cards into the list, and keeps a page the church edited."""

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("Web Page", "sermons"):
			self.skipTest("The site has no sermons Web Page.")

	def page(self):
		return frappe.db.get_value("Web Page", "sermons", "main_section_html")

	def test_the_shipped_cards_become_the_list(self):
		frappe.db.set_value(
			"Web Page", "sermons", "main_section_html", "\n" + list_sermons_one_a_row.SHIPPED_SERMONS
		)

		list_sermons_one_a_row.execute()
		list_sermons_one_a_row.execute()

		self.assertEqual(self.page(), read_template("sermons.html"))

	def test_an_edited_page_keeps_its_cards(self):
		edited = list_sermons_one_a_row.SHIPPED_SERMONS.replace("Please check back soon.", "Soon!")
		frappe.db.set_value("Web Page", "sermons", "main_section_html", edited)

		list_sermons_one_a_row.execute()

		self.assertEqual(self.page(), edited)


class TestFooterLinks(RollbackEachTest):
	def footer_urls(self):
		return [row.url for row in frappe.get_doc("Website Settings").footer_items]

	def set_footer(self, items):
		settings = frappe.get_doc("Website Settings")
		settings.footer_items = []
		for item in items:
			settings.append("footer_items", item)
		# Tests skip Versions by default; the patch reads them.
		settings.save(ignore_permissions=True, ignore_version=False)

	def test_install_links_the_guest_pages_from_the_footer(self):
		after_install._setup_website_settings()

		self.assertEqual(
			self.footer_urls(), ["/connection-card/new", "/prayer-request-anonymous/new", "/portal"]
		)

	def clear_footer_history(self):
		"""An empty footer that no saved change emptied, as on a site installed before the footer links."""
		frappe.db.delete("Top Bar Item", {"parent": "Website Settings", "parentfield": "footer_items"})
		frappe.db.delete("Version", {"ref_doctype": "Website Settings"})
		frappe.clear_document_cache("Website Settings", "Website Settings")

	def test_the_patch_fills_only_an_empty_footer(self):
		self.clear_footer_history()
		add_website_footer_links.execute()
		add_website_footer_links.execute()
		self.assertEqual(self.footer_urls(), [item["url"] for item in after_install.FOOTER_ITEMS])

		self.set_footer([{"label": "Our Story", "url": "/about"}])
		add_website_footer_links.execute()
		self.assertEqual(self.footer_urls(), ["/about"])

	def test_the_patch_leaves_a_footer_that_someone_emptied_empty(self):
		self.clear_footer_history()
		self.set_footer([{"label": "Our Story", "url": "/about"}])
		self.set_footer([])

		add_website_footer_links.execute()

		self.assertEqual(self.footer_urls(), [])

	def test_the_login_page_shows_the_church_s_footer(self):
		frappe.db.delete("Version", {"ref_doctype": "Website Settings"})
		frappe.db.set_single_value("Website Settings", "show_footer_on_login", 0)
		show_footer_on_login_page.execute()
		show_footer_on_login_page.execute()
		self.assertEqual(frappe.db.get_single_value("Website Settings", "show_footer_on_login"), 1)

	def test_the_login_patch_keeps_a_church_s_own_choice(self):
		frappe.db.delete("Version", {"ref_doctype": "Website Settings"})
		settings = frappe.get_doc("Website Settings")
		settings.show_footer_on_login = 1
		settings.save(ignore_permissions=True, ignore_version=False)
		settings.show_footer_on_login = 0
		settings.save(ignore_permissions=True, ignore_version=False)

		show_footer_on_login_page.execute()

		self.assertEqual(frappe.db.get_single_value("Website Settings", "show_footer_on_login"), 0)

	def test_a_switched_off_page_loses_its_footer_link(self):
		self.assertTrue(is_link_off("/connection-card/new", {"connection-card"}))
		self.assertTrue(is_link_off("/prayer-request-anonymous/new", {"prayer-request-anonymous"}))
