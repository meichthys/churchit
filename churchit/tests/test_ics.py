# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The iCalendar building blocks and the public church calendar feed."""

from urllib.parse import urlencode

import frappe
from frappe.utils import add_days, getdate, set_request

from churchit.church_website.published_fields import PUBLIC, published_field_map
from churchit.ics import calendar_text, calendar_times, fold, get_public_calendar
from churchit.tests.helpers import RollbackEachTest, ensure, make_address, make_function, make_two_churches

FEED_ROUTE = "api/method/churchit.ics.get_public_calendar"


def request_feed(case, feed, etag=None, **query):
	"""Call *feed* the way a calendar app does: a GET with *query*, sending *etag* back when it has one."""
	saved = getattr(frappe.local, "request", None), frappe.local.request_ip
	case.addCleanup(
		lambda: (setattr(frappe.local, "request", saved[0]), setattr(frappe.local, "request_ip", saved[1]))
	)
	set_request(method="GET", query_string=urlencode(query), headers={"If-None-Match": etag} if etag else {})
	# A fresh address for each call keeps reruns under the rate limit.
	frappe.local.request_ip = frappe.generate_hash(length=12)
	frappe.local.form_dict = frappe._dict(query)
	return frappe.call(feed, **query)


def unfold(response):
	return response.get_data(as_text=True).replace("\r\n ", "")


class TestCalendarText(RollbackEachTest):
	def test_a_long_non_ascii_line_folds_into_75_octets_and_unfolds_unchanged(self):
		line = "SUMMARY:" + "Gebetstreffen für Ältere 祈祷会 🙏 " * 7
		self.assertGreater(len(line), 200)

		folded = fold(line)
		for part in folded.split("\r\n"):
			self.assertLessEqual(len(part.encode()), 75, part)
		self.assertEqual(folded.replace("\r\n ", ""), line)

	def test_a_short_line_is_left_alone(self):
		self.assertEqual(fold("SUMMARY:Sunday"), "SUMMARY:Sunday")

	def test_an_all_day_function_fills_whole_days_and_text_is_escaped(self):
		retreat = frappe._dict(start_date="2031-05-02", end_date="2031-05-04", all_day=1)
		self.assertEqual(
			calendar_times(retreat), ["DTSTART;VALUE=DATE:20310502", "DTEND;VALUE=DATE:20310505"]
		)
		self.assertEqual(
			calendar_text("Ushers, Greeters; Doors\\Halls\nTwo"), "Ushers\\, Greeters\\; Doors\\\\Halls\\nTwo"
		)
		self.assertEqual(calendar_text("One\r\nTwo\rThree"), "One\\nTwo\\nThree")


class TestPublicCalendar(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_a, "publish", 1)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def function(self, name, **values):
		values.setdefault("church", self.branch_a)
		return make_function(name, start_date=add_days(getdate(), 3), **values)

	def feed(self, etag=None, **query):
		frappe.set_user("Guest")
		try:
			return request_feed(self, get_public_calendar, etag=etag, church=self.branch_a, **query)
		finally:
			frappe.set_user("Administrator")

	def test_a_long_non_ascii_title_validates_as_folded_lines(self):
		title = ("Gebetstreffen für Ältere 祈祷会 🙏 " * 4).strip()
		self.function(title, publish=1, description="Für alle, die beten möchten. 祈祷会 " * 6)

		response = self.feed()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.mimetype, "text/calendar")
		for line in response.get_data(as_text=True).split("\r\n"):
			self.assertLessEqual(len(line.encode()), 75, line)
		self.assertIn(f"SUMMARY:{title}", unfold(response))

	def test_an_unchanged_feed_keeps_its_etag_and_answers_304(self):
		self.function("_Test Feed Etag", publish=1)

		first = self.feed()
		second = self.feed()
		self.assertTrue(first.get_etag()[0])
		self.assertEqual(first.get_etag(), second.get_etag())

		cached = self.feed(etag=f'"{first.get_etag()[0]}"')
		self.assertEqual(cached.status_code, 304)
		self.assertEqual(cached.get_data(), b"")

	def test_unpublished_and_another_churchs_functions_are_left_out(self):
		mine = self.function("_Test Feed Mine", publish=1)
		self.function("_Test Feed Draft", publish=0)
		self.function("_Test Feed Theirs", publish=1, church=self.branch_b)
		joint = self.function("_Test Feed Joint", publish=1, church=self.branch_b, is_shared=1)

		feed = unfold(self.feed())
		self.assertIn(f"UID:{mine.name}@", feed)
		self.assertIn(f"UID:{joint.name}@", feed)
		self.assertNotIn("_Test Feed Draft", feed)
		self.assertNotIn("_Test Feed Theirs", feed)

	def test_a_ministry_lists_only_its_own_published_functions(self):
		published = ensure("Ministry", {"ministry_name": "_Test Feed Ministry", "publish": 1})
		hidden = ensure("Ministry", {"ministry_name": "_Test Feed Hidden Ministry", "publish": 0})
		self.function("_Test Feed Ministry Night", publish=1, associated_ministry=published)
		self.function("_Test Feed Hidden Night", publish=1, associated_ministry=hidden)
		self.function("_Test Feed Other Night", publish=1)

		feed = unfold(self.feed(ministry=published))
		self.assertIn("_Test Feed Ministry Night", feed)
		self.assertNotIn("_Test Feed Hidden Night", feed)
		self.assertNotIn("_Test Feed Other Night", feed)

		self.assertNotIn("BEGIN:VEVENT", unfold(self.feed(ministry=hidden)))

	def test_a_crlf_description_has_no_bare_carriage_return(self):
		self.function(
			"_Test Feed Crlf", publish=1, description="Bring a Bible.\r\nCoffee after.\rAll welcome."
		)

		feed = unfold(self.feed())
		self.assertIn("DESCRIPTION:Bring a Bible.\\nCoffee after.\\nAll welcome.", feed)
		self.assertNotIn("\r", feed.replace("\r\n", ""))

	def test_a_function_with_an_address_has_a_location(self):
		address = make_address(
			"_Test Feed Venue", address_line1="12 Chapel Rd", city="Springfield", state="IL"
		)
		self.function("_Test Feed Venue Night", publish=1, address=address.name)

		self.assertIn("LOCATION:12 Chapel Rd\\, Springfield\\, IL\\, United States", unfold(self.feed()))

	def test_a_link_only_function_is_left_out(self):
		listed = self.function("_Test Feed Listed", publish=1)
		self.function("_Test Feed Link Only", publish=1, is_link_only=1)

		feed = unfold(self.feed())
		self.assertIn(f"UID:{listed.name}@", feed)
		self.assertNotIn("_Test Feed Link Only", feed)

	def test_a_meeting_link_is_the_event_url(self):
		self.function("_Test Feed Online", publish=1, meeting_url="https://meet.example.org/a,b;c")
		self.function("_Test Feed In Person", publish=1)

		feed = unfold(self.feed())
		self.assertIn("URL:https://meet.example.org/a,b;c\r\n", feed)
		self.assertEqual(feed.count("URL:"), 1)

	def test_a_stored_meeting_link_with_a_line_break_adds_no_line(self):
		function = self.function("_Test Feed Broken Link", publish=1)
		frappe.db.set_value("Function", function.name, "meeting_url", "https://x.org/a\r\nX-INJECT:1")

		feed = unfold(self.feed())
		self.assertIn(f"UID:{function.name}@", feed)
		self.assertNotIn("X-INJECT", feed)
		self.assertNotIn("URL:", feed)

	def test_the_feed_fields_carry_the_public_badge(self):
		published = published_field_map()["Function"]
		for fieldname in (
			"function_name",
			"start_date",
			"start_time",
			"end_date",
			"address",
			"description",
			"meeting_url",
		):
			sources = [source for source in published[fieldname] if source["route"] == FEED_ROUTE]
			self.assertEqual([source["access"] for source in sources], [PUBLIC], fieldname)
