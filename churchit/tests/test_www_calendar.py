# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import timedelta

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_months, getdate

from churchit.tests.helpers import make_address, make_function
from churchit.www.calendar import _combine, _format_address, get_context, get_events


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
		all_day = make_function("_Test All Day", start_date=getdate(), all_day=1, start_time="09:00:00", publish=1)

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
