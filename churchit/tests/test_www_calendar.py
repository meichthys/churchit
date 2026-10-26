# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import re
from datetime import timedelta
from html import escape
from urllib.parse import urlencode

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_months, getdate, set_request
from frappe.website.serve import get_response

from churchit.church_website.published_fields import PUBLIC, published_field_map
from churchit.patches.after_install import read_template
from churchit.patches.v1_0 import hide_link_only_functions_on_home_page
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_root_church,
	force_single_church,
	make_address,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.tests.test_ics import request_feed
from churchit.www.calendar import _combine, _format_address, get_context, get_event, get_events


class TestCalendarPage(FrappeTestCase):
	def _events(self, start=None, end=None):
		start = start or add_days(getdate(), -1)
		end = end or add_days(getdate(), 1)
		return {event["id"]: event for event in get_events(start, end)}

	def test_context_exposes_the_public_window(self):
		context = frappe._dict()
		get_context(context)
		self.assertEqual(context.window_start, add_months(getdate(), -1))
		self.assertEqual(context.window_end, add_months(getdate(), 6))

	def test_only_published_functions_in_range_are_returned(self):
		published = make_function("_Test Public Event", start_date=getdate(), publish=1)
		make_function("_Test Private Event", start_date=getdate(), publish=0)
		out_of_range = make_function("_Test Later Event", start_date=add_days(getdate(), 10), publish=1)

		events = self._events()
		self.assertIn(published.name, events)
		self.assertNotIn(out_of_range.name, events)
		self.assertEqual(len([e for e in events.values() if e["title"] == "_Test Private Event"]), 0)

	def test_a_function_that_starts_before_the_range_and_ends_inside_it_is_listed(self):
		ongoing = make_function(
			"_Test Ongoing Camp", start_date=add_days(getdate(), -5), end_date=getdate(), publish=1
		)
		finished = make_function(
			"_Test Finished Camp",
			start_date=add_days(getdate(), -5),
			end_date=add_days(getdate(), -3),
			publish=1,
		)
		one_day = make_function("_Test Past Day", start_date=add_days(getdate(), -3), publish=1)

		events = self._events()
		self.assertIn(ongoing.name, events)
		self.assertNotIn(finished.name, events)
		self.assertNotIn(one_day.name, events)

	def test_requests_are_clamped_to_the_public_window(self):
		old = make_function("_Test Ancient Event", start_date=add_months(getdate(), -2), publish=1)
		far = make_function("_Test Distant Event", start_date=add_months(getdate(), 8), publish=1)
		events = self._events(start=add_months(getdate(), -12), end=add_months(getdate(), 12))
		self.assertNotIn(old.name, events)
		self.assertNotIn(far.name, events)

	def test_event_shape_for_timed_and_all_day_functions(self):
		address = make_address("_Test Venue", address_line1="12 Chapel Rd", city="Springfield", state="IL")
		timed = make_function(
			"_Test Timed",
			start_date=getdate(),
			start_time="09:30:00",
			end_time="10:30:00",
			publish=1,
			address=address.name,
			description="Bring a friend",
		)
		all_day = make_function(
			"_Test All Day", start_date=getdate(), all_day=1, start_time="09:00:00", publish=1
		)

		events = self._events()
		self.assertEqual(events[timed.name]["start"], f"{getdate()}T09:30:00")
		self.assertEqual(events[timed.name]["end"], f"{getdate()}T10:30:00")
		self.assertFalse(events[timed.name]["allDay"])
		self.assertEqual(events[timed.name]["address"], "12 Chapel Rd, Springfield, IL, United States")
		self.assertEqual(events[timed.name]["description"], "Bring a friend")

		self.assertEqual(events[all_day.name]["start"], str(getdate()))
		self.assertTrue(events[all_day.name]["allDay"])
		self.assertIsNone(events[all_day.name]["address"])

	def test_combine_and_format_helpers(self):
		self.assertIsNone(_combine(None, "09:00:00", 0))
		self.assertEqual(_combine("2030-01-01", "09:00:00", 1), "2030-01-01")
		self.assertEqual(_combine("2030-01-01", None, 0), "2030-01-01")
		self.assertEqual(_combine("2030-01-01", "09:00:00", 0), "2030-01-01T09:00:00")
		self.assertEqual(_combine("2030-01-01", timedelta(hours=9), 0), "2030-01-01T09:00:00")

		cache = {}
		self.assertIsNone(_format_address(None, cache))
		self.assertEqual(_format_address("ADDR-MISSING", cache), "ADDR-MISSING")
		self.assertEqual(cache, {"ADDR-MISSING": "ADDR-MISSING"})


def events_today(**args):
	today = getdate()
	return {event["id"]: event for event in get_events(add_days(today, -1), add_days(today, 1), **args)}


def calendar_badge(doctype, fieldname):
	"""Who sees *fieldname* of *doctype* on /calendar."""
	sources = published_field_map().get(doctype, {}).get(fieldname, [])
	return [source["access"] for source in sources if source["route"] == "calendar"]


class TestCalendarRooms(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.function = make_function("_Test Calendar Rooms", start_date=getdate(), publish=1)
		self.requester = make_person("_Test Calendar Booker").name

	def room(self, room_name, requires_approval=0):
		values = {"room_name": room_name, "is_bookable": 1, "requires_approval": requires_approval}
		return ensure("Room", {"room_name": room_name}, values)

	def book(self, room, hour, **values):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"function": self.function.name,
				"requester": self.requester,
				"purpose": "Calendar test",
				"start_datetime": f"2032-02-03 {hour:02d}:00:00",
				"end_datetime": f"2032-02-03 {hour + 1:02d}:00:00",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_an_approved_booking_shows_its_room_name(self):
		booking = self.book(self.room("_Test Calendar Hall"), 9)
		self.assertEqual(booking.status, "Approved")

		self.assertEqual(events_today()[self.function.name]["rooms"], ["_Test Calendar Hall"])

	def test_a_requested_or_denied_booking_shows_no_room(self):
		requested = self.book(self.room("_Test Calendar Gated Hall", requires_approval=1), 10)
		denied = self.book(self.room("_Test Calendar Denied Hall"), 11, status="Denied")
		self.assertEqual((requested.status, denied.status), ("Requested", "Denied"))

		self.assertEqual(events_today()[self.function.name]["rooms"], [])

	def test_the_room_name_carries_the_public_badge(self):
		self.assertEqual(calendar_badge("Room", "room_name"), [PUBLIC])


class TestCalendarRoomOfAnotherChurch(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_a, "publish", 1)
		frappe.db.set_value("Church", cls.branch_b, "publish", 0)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict(church=self.branch_a)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def book(self, function, church, room_name, hour):
		room = ensure(
			"Room", {"room_name": room_name}, {"room_name": room_name, "is_bookable": 1, "church": church}
		)
		self.addCleanup(frappe.db.delete, "Room Booking", {"room": room})
		frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": room,
				"function": function,
				"church": church,
				"requester": make_person(f"_Test Booker {room_name}", church=church).name,
				"purpose": "Calendar test",
				"start_datetime": f"2032-02-04 {hour:02d}:00:00",
				"end_datetime": f"2032-02-04 {hour + 1:02d}:00:00",
			}
		).insert(ignore_permissions=True)

	def test_a_booking_by_another_church_shows_no_room(self):
		function = make_function(
			"_Test Calendar Rooms Of A", start_date=getdate(), publish=1, church=self.branch_a
		)
		self.book(function.name, self.branch_a, "_Test Calendar Hall Of A", 9)
		self.book(function.name, self.branch_b, "_Test Calendar Secret Hall Of B", 10)

		self.assertEqual(events_today()[function.name]["rooms"], ["_Test Calendar Hall Of A"])


class TestCalendarMap(RollbackEachTest):
	def test_an_address_with_coordinates_gives_a_pin_and_a_map_link(self):
		address = make_address("_Test Calendar Placed", latitude=39.781721, longitude=-89.650148)
		placed = make_function("_Test Calendar Placed", start_date=getdate(), publish=1, address=address.name)

		event = events_today()[placed.name]
		self.assertEqual(event["coordinates"], [39.781721, -89.650148])
		self.assertTrue(event["map_url"].startswith("https://www.openstreetmap.org/search?"))

	def test_an_address_without_coordinates_gives_no_pin(self):
		address = make_address("_Test Calendar Unplaced")
		unplaced = make_function(
			"_Test Calendar Unplaced", start_date=getdate(), publish=1, address=address.name
		)
		nowhere = make_function("_Test Calendar Nowhere", start_date=getdate(), publish=1)

		events = events_today()
		self.assertIsNone(events[unplaced.name]["coordinates"])
		self.assertIsNotNone(events[unplaced.name]["map_url"])
		self.assertIsNone(events[nowhere.name]["coordinates"])
		self.assertIsNone(events[nowhere.name]["map_url"])

	def test_the_coordinates_carry_the_public_badge(self):
		for fieldname in ("latitude", "longitude"):
			self.assertEqual(calendar_badge("Address", fieldname), [PUBLIC], fieldname)


class TestLinkOnlyAndBranches(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.root, "publish", 1)
		frappe.db.set_value("Church", cls.branch_a, "publish", 1)
		frappe.db.set_value("Church", cls.branch_b, "publish", 0)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict(church=self.root)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def function(self, name, church=None, **values):
		values.setdefault("publish", 1)
		return make_function(name, start_date=getdate(), church=church or self.root, **values)

	def event(self, name):
		frappe.set_user("Guest")
		try:
			return request_feed(self, get_event, name=name)
		finally:
			frappe.set_user("Administrator")

	def test_a_link_only_function_is_left_off_the_calendar_but_opens_by_its_link(self):
		hidden = self.function("_Test Calendar Link Only", is_link_only=1)
		shown = self.function("_Test Calendar Listed")

		events = events_today()
		self.assertNotIn(hidden.name, events)
		self.assertIn(shown.name, events)
		self.assertEqual(self.event(hidden.name)["title"], "_Test Calendar Link Only")

	def test_an_unpublished_function_or_church_gives_no_event(self):
		draft = self.function("_Test Calendar Draft", publish=0)
		closed = self.function("_Test Calendar Closed Branch", church=self.branch_b)

		self.assertIsNone(self.event(draft.name))
		self.assertIsNone(self.event(closed.name))
		self.assertIsNone(self.event("FUNC-NOT-THERE"))

	def test_the_main_church_shows_published_branches_only_when_asked(self):
		branch = self.function("_Test Calendar Branch Night", church=self.branch_a)
		closed = self.function("_Test Calendar Closed Night", church=self.branch_b)
		shared = self.function("_Test Calendar Shared Night", church=self.branch_b, is_shared=1)

		self.assertNotIn(branch.name, events_today())
		events = events_today(include_branches="1")
		self.assertIn(branch.name, events)
		self.assertIn(shared.name, events)
		self.assertNotIn(closed.name, events)
		self.assertEqual(
			events[branch.name]["church_name"], frappe.db.get_value("Church", self.branch_a, "church_name")
		)

	def test_the_branch_toggle_shows_only_when_a_published_branch_exists(self):
		context = frappe._dict()
		get_context(context)
		self.assertTrue(context.has_branches)

		frappe.local.form_dict = frappe._dict(church=self.branch_a)
		get_context(context)
		self.assertFalse(context.has_branches)

	def test_the_home_page_leaves_out_link_only_functions(self):
		self.function("_Test Calendar Home Hidden", is_link_only=1)
		self.function("_Test Calendar Home Listed", start_time="00:00:01")

		html = frappe.render_template(read_template("home.html"), {})
		self.assertIn("_Test Calendar Home Listed", html)
		self.assertNotIn("_Test Calendar Home Hidden", html)

	def test_the_patch_hides_link_only_functions_on_an_existing_home_page(self):
		scoped = 'filters=selected_church_filters(publish=1, start_date=[">=", frappe.utils.nowdate()])'
		page = frappe.get_doc("Web Page", "home")
		page.main_section_html = f"<p>Our own hero</p>\n{scoped}"
		page.save(ignore_permissions=True)

		hide_link_only_functions_on_home_page.execute()
		hide_link_only_functions_on_home_page.execute()

		html = frappe.db.get_value("Web Page", "home", "main_section_html")
		self.assertIn("<p>Our own hero</p>", html)
		self.assertEqual(html.count("is_link_only=0"), 1)


class TestLinkOnlyOnOneChurch(RollbackEachTest):
	def test_a_link_only_function_opens_by_its_link_when_the_church_is_not_published(self):
		force_single_church()
		frappe.db.set_value("Church", ensure_root_church(), "publish", 0)
		hidden = make_function(
			"_Test Calendar Single Link Only", start_date=getdate(), publish=1, is_link_only=1
		)

		self.assertNotIn(hidden.name, events_today())
		frappe.set_user("Guest")
		self.assertEqual(request_feed(self, get_event, name=hidden.name)["id"], hidden.name)


class TestCalendarSubscribeLinks(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, _branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		frappe.db.set_value("Church", cls.branch_a, "publish", 1)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict(church=self.branch_a)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def test_both_links_name_the_selected_church_feed(self):
		context = frappe._dict()
		get_context(context)

		path = "/api/method/churchit.ics.get_public_calendar?" + urlencode({"church": self.branch_a})
		self.assertTrue(context.feed_url.startswith("http"))
		self.assertTrue(context.feed_url.endswith(path), context.feed_url)
		self.assertTrue(context.webcal_url.startswith("webcal://"))
		self.assertEqual(context.webcal_url.partition("://")[2], context.feed_url.partition("://")[2])

	def test_the_page_offers_both_links(self):
		frappe.set_user("Guest")
		set_request(method="GET", path="calendar", query_string=urlencode({"church": self.branch_a}))
		self.addCleanup(setattr, frappe.local, "request", None)
		frappe.local.form_dict = frappe._dict(church=self.branch_a)
		html = get_response("calendar").get_data(as_text=True)

		path = "/api/method/churchit.ics.get_public_calendar?" + escape(urlencode({"church": self.branch_a}))
		self.assertRegex(html, rf'href="webcal://[^/"]+{re.escape(path)}">')
		self.assertRegex(html, rf'href="https?://[^/"]+{re.escape(path)}" download')


class TestCalendarMeetingLink(RollbackEachTest):
	def test_a_published_function_sends_its_meeting_link(self):
		online = make_function(
			"_Test Calendar Online",
			start_date=getdate(),
			publish=1,
			meeting_url="https://meet.example.org/abc",
		)
		self.assertEqual(events_today()[online.name]["meeting_url"], "https://meet.example.org/abc")
		self.assertEqual(calendar_badge("Function", "meeting_url"), [PUBLIC])
