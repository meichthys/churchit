# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.handler import execute_cmd
from frappe.utils import add_days, now_datetime, set_request
from frappe.website.serve import get_response

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CONFIRMED,
	PENDING,
	WAITLISTED,
)
from churchit.ics import calendar_times
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.tests.test_ics import request_feed, unfold
from churchit.www.register import (
	MAX_ATTENDEES,
	get_attendee_choices,
	get_attendee_rows,
	get_calendar_link,
	get_event_calendar,
	sign_up,
)

ROUTE = "register"
SIGN_UP = "Function Sign-Up"
METHOD = "churchit.www.register.sign_up"


class RegisterTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		for church in (cls.church, cls.other_church):
			frappe.db.set_value("Church", church, "publish", 1)
		guest_open = {"allow_sign_ups": 1, "publish": 1, "allow_guest_sign_ups": 1}
		cls.function = make_function("_Test Register Retreat", church=cls.church, **guest_open).name
		cls.members_only = make_function(
			"_Test Register Members Only", church=cls.church, allow_sign_ups=1, publish=1
		).name
		cls.theirs = make_function("_Test Register Theirs", church=cls.other_church, **guest_open).name
		# Someone already signed up, whose name no guest may see.
		cls.member = make_person("_Test Hidden", "Registrant", church=cls.church)
		frappe.get_doc({"doctype": SIGN_UP, "function": cls.function, "person": cls.member.name}).insert(
			ignore_permissions=True
		)

	def setUp(self):
		super().setUp()
		enqueue = patch("frappe.enqueue")
		enqueue.start()
		self.addCleanup(enqueue.stop)

	def tearDown(self):
		frappe.local.form_dict = frappe._dict()
		super().tearDown()

	def serve(self, **query):
		frappe.set_user("Guest")
		query = {"church": self.church, **query}
		set_request(method="GET", path=ROUTE, query_string="&".join(f"{k}={v}" for k, v in query.items()))
		self.addCleanup(setattr, frappe.local, "request", None)
		frappe.local.form_dict = frappe._dict(query)
		return get_response(ROUTE).get_data(as_text=True)

	def register(self, function=None, **values):
		"""Call sign_up as a guest from the page of the test church."""
		frappe.set_user("Guest")
		frappe.local.form_dict = frappe._dict(church=self.church)
		values = {"registrant_name": "_Test Rita Register", "email": "_test_rita@example.com", **values}
		try:
			return sign_up(function or self.function, **values)
		finally:
			frappe.set_user("Administrator")

	def set_window(self, opens=None, closes=None):
		frappe.db.set_value(
			"Function", self.function, {"sign_ups_open_on": opens, "sign_ups_close_on": closes}
		)


class TestRegisterPage(RegisterTestCase):
	def test_the_page_lists_only_the_selected_churchs_functions_open_to_guests(self):
		html = self.serve()

		self.assertIn("_Test Register Retreat", html)
		self.assertNotIn("_Test Register Members Only", html)
		self.assertNotIn("_Test Register Theirs", html)

	def test_the_form_shows_the_function_and_no_registrant_name(self):
		html = self.serve(function=self.function)

		self.assertIn('name="registrant_name"', html)
		self.assertIn("_Test Register Retreat", html)
		self.assertNotIn(self.member.full_name, html)

	def test_a_link_only_function_is_not_listed_but_opens_by_its_link(self):
		frappe.db.set_value("Function", self.function, "is_link_only", 1)

		self.assertNotIn("_Test Register Retreat", self.serve())
		html = self.serve(function=self.function)
		self.assertIn('name="registrant_name"', html)
		self.assertIn("_Test Register Retreat", html)

	def test_a_function_outside_its_window_is_not_offered(self):
		self.set_window(opens=add_days(now_datetime(), 1))
		self.assertNotIn("_Test Register Retreat", self.serve())
		self.set_window(closes=add_days(now_datetime(), -1))
		html = self.serve(function=self.function)
		self.assertNotIn('name="registrant_name"', html)


class TestRegisterSignUp(RegisterTestCase):
	def test_a_guest_sign_up_stores_one_confirmed_sign_up_with_what_the_guest_typed(self):
		response = self.register(phone="555 0142", notes="_Test vegetarian", discount_code="_TESTCODE")

		self.assertEqual(response["status"], CONFIRMED)
		sign_up = frappe.get_doc(
			SIGN_UP, {"function": self.function, "registrant_name": "_Test Rita Register"}
		)
		self.assertEqual(
			(sign_up.status, sign_up.person, sign_up.email, sign_up.phone, sign_up.notes, sign_up.church),
			(CONFIRMED, None, "_test_rita@example.com", "555 0142", "_Test vegetarian", self.church),
		)
		self.assertEqual(sign_up.discount_code, "_TESTCODE")
		self.assertEqual(sign_up.owner, "Guest")

	def test_the_response_names_no_existing_person_who_matches(self):
		response = frappe.as_json(self.register(registrant_name="_Test H. Registrant"))
		self.assertNotIn(self.member.full_name, response)
		self.assertNotIn(self.member.name, response)

	def test_a_guest_cannot_sign_up_for_a_function_not_open_to_guests(self):
		for function in (self.members_only, self.theirs):
			with self.assertRaises(frappe.PermissionError):
				self.register(function)

	def test_a_guest_cannot_sign_up_before_the_window_opens_or_after_it_closes(self):
		self.set_window(opens=add_days(now_datetime(), 1))
		with self.assertRaises(frappe.PermissionError):
			self.register()
		self.set_window(opens=add_days(now_datetime(), -2), closes=add_days(now_datetime(), -1))
		with self.assertRaises(frappe.PermissionError):
			self.register()
		self.set_window(opens=add_days(now_datetime(), -2), closes=add_days(now_datetime(), 1))
		self.assertEqual(self.register()["status"], CONFIRMED)

	def test_an_invalid_email_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.register(email="not an email")

	def test_a_filled_honeypot_stores_nothing(self):
		before = frappe.db.count(SIGN_UP)
		self.assertEqual(self.register(website="http://spam.example.com"), {"status": CONFIRMED})
		self.assertEqual(frappe.db.count(SIGN_UP), before)

	def test_sign_up_refuses_a_get(self):
		"""A GET carries no CSRF token, so another site could sign visitors up from their browser."""
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(method="GET")
		self.addCleanup(delattr, frappe.local, "request")
		frappe.local.form_dict = frappe._dict(
			church=self.church,
			function=self.function,
			registrant_name="_Test Rita Register",
			email="_test_rita@example.com",
		)
		before = frappe.db.count(SIGN_UP)

		with self.assertRaises(frappe.PermissionError):
			execute_cmd(METHOD)

		self.assertEqual(frappe.db.count(SIGN_UP), before)

	def test_the_endpoint_passes_every_form_value_to_the_extension_points(self):
		frappe.set_user("Guest")
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = "_test_register"
		self.addCleanup(delattr, frappe.local, "request")
		self.addCleanup(frappe.cache.delete_keys, "rl:")
		frappe.local.form_dict = frappe._dict(
			church=self.church,
			function=self.function,
			registrant_name="_Test Rita Register",
			email="_test_rita@example.com",
			household="[]",
		)
		with patch("churchit.www.register.get_attendee_rows", return_value=[]) as get_attendee_rows:
			execute_cmd(METHOD)

		self.assertEqual(get_attendee_rows.call_args.args[1]["household"], "[]")


class TestRegisterCalendar(RegisterTestCase):
	def fetch_calendar(self, function, church=None):
		frappe.set_user("Guest")
		return request_feed(self, get_event_calendar, function=function, church=church or self.church)

	def test_a_confirmed_sign_up_links_to_its_event(self):
		response = self.register()

		query = parse_qs(urlparse(response["calendar_url"]).query)
		self.assertEqual(query["function"], [self.function])
		feed = self.fetch_calendar(**{key: values[0] for key, values in query.items()})
		self.assertEqual(feed.mimetype, "text/calendar")
		calendar = unfold(feed)
		function = frappe.get_doc("Function", self.function)
		self.assertIn(calendar_times(function)[0], calendar.split("\r\n"))
		self.assertIn("SUMMARY:_Test Register Retreat", calendar)

	def test_a_sign_up_that_is_not_confirmed_gets_no_calendar_link(self):
		for status in (PENDING, WAITLISTED):
			self.assertEqual(get_calendar_link(frappe._dict(status=status, function=self.function)), {})

	def test_only_a_function_register_offers_gives_a_calendar(self):
		unpublished = make_function("_Test Register Hidden", church=self.church, publish=0).name
		guest_open = {"allow_sign_ups": 1, "publish": 1, "allow_guest_sign_ups": 1}
		past = add_days(now_datetime(), -60).date()
		past = make_function("_Test Register Past", church=self.church, start_date=past, **guest_open).name
		for function in (unpublished, past, self.members_only, self.theirs):
			with self.assertRaises(frappe.DoesNotExistError):
				self.fetch_calendar(function)

		self.assertEqual(self.fetch_calendar(self.theirs, church=self.other_church).status_code, 200)


class TestRegisterAttendees(RegisterTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Register Household"})
		family = family.insert(ignore_permissions=True).name
		cls.user = ensure_user("_test_register_member@example.com", "_Test Member")
		household = {"church": cls.church, "family": family}
		cls.own = make_person("_Test Mara", "Household", user=cls.user, **household).name
		cls.spouse = make_person("_Test Spouse", "Household", **household)
		cls.child = make_person("_Test Child", "Household", **household)
		neighbors = frappe.get_doc({"doctype": "Family", "family_name": "_Test Register Neighbors"})
		neighbors = neighbors.insert(ignore_permissions=True).name
		cls.neighbor = make_person("_Test Neighbor", "Next Door", church=cls.church, family=neighbors)

	def register_as_member(self, **values):
		frappe.set_user(self.user)
		frappe.local.form_dict = frappe._dict(church=self.church)
		values = {"registrant_name": "_Test Mara Household", "email": "_test_mara@example.com", **values}
		return sign_up(self.function, **values)

	def choices(self, user="Guest", function=None):
		frappe.set_user(user)
		return request_feed(
			self, get_attendee_choices, function=function or self.function, church=self.church
		)

	def attendees_of(self, registrant_name):
		sign_up = frappe.get_doc(SIGN_UP, {"function": self.function, "registrant_name": registrant_name})
		return {(row.person, row.attendee_name) for row in sign_up.attendees}

	def test_a_member_is_offered_the_other_people_of_their_household_and_a_guest_nobody(self):
		household = self.choices(self.user)["household"]

		self.assertEqual(
			{(row["person"], row["full_name"]) for row in household},
			{(self.spouse.name, self.spouse.full_name), (self.child.name, self.child.full_name)},
		)
		self.assertEqual(self.choices()["household"], [])

	def test_a_member_adds_the_household_members_they_ticked(self):
		self.register_as_member(attendees=json.dumps([{"person": self.child.name}]))

		self.assertIn((self.child.name, self.child.full_name), self.attendees_of("_Test Mara Household"))

	def test_naming_a_person_of_another_household_is_refused(self):
		before = frappe.db.count(SIGN_UP)
		for person in (self.neighbor.name, self.own):
			with self.assertRaises(frappe.PermissionError):
				self.register_as_member(attendees=json.dumps([{"person": person}]))
		with self.assertRaises(frappe.PermissionError):
			self.register(attendees=json.dumps([{"person": self.spouse.name}]))

		self.assertEqual(frappe.db.count(SIGN_UP), before)

	def test_a_guest_types_the_names_of_the_others_who_come(self):
		self.register(attendees=json.dumps([{"attendee_name": " _Test Tim Typed "}, {"attendee_name": ""}]))

		self.assertIn((None, "_Test Tim Typed"), self.attendees_of("_Test Rita Register"))

	def test_attendees_that_cannot_be_read_or_too_many_are_refused(self):
		too_many = [{"attendee_name": f"_Test Guest {index}"} for index in range(MAX_ATTENDEES + 1)]
		for attendees in ("{not json", '{"person": "x"}', "[1]", json.dumps(too_many)):
			with self.assertRaises(frappe.ValidationError):
				self.register(attendees=attendees)

	def test_on_a_function_with_selections_the_registrant_row_takes_the_chosen_selection(self):
		function = frappe.get_doc("Function", self.function)
		function.append("selections", {"selection": "_Test Adult"})
		function.append("selections", {"selection": "_Test Child"})
		attendees = json.dumps([{"person": self.child.name, "selection": "_Test Child"}])
		form = {"selection": "_Test Adult", "attendees": attendees, "registrant_name": "_Test Mara Household"}

		frappe.set_user(self.user)
		self.assertEqual(
			get_attendee_rows(function, form),
			[
				{"person": self.own, "attendee_name": None, "selection": "_Test Adult"},
				{"person": self.child.name, "attendee_name": None, "selection": "_Test Child"},
			],
		)
		frappe.set_user("Guest")
		self.assertEqual(
			get_attendee_rows(function, {**form, "attendees": "[]"}),
			[{"person": None, "attendee_name": "_Test Mara Household", "selection": "_Test Adult"}],
		)

	def test_a_guest_on_a_function_with_selections_keeps_the_selection_they_chose(self):
		for selection in ("_Test Adult", "_Test Child"):
			frappe.get_doc(
				{
					"doctype": "Function Sign-Up Selection",
					"parent": self.function,
					"parenttype": "Function",
					"parentfield": "selections",
					"selection": selection,
				}
			).insert(ignore_permissions=True)
		attendees = json.dumps([{"attendee_name": "_Test Tim Typed", "selection": "_Test Child"}])

		self.register(registrant_name=" _Test Rita Register ", selection="_Test Adult", attendees=attendees)

		sign_up = frappe.get_doc(
			SIGN_UP, {"function": self.function, "registrant_name": "_Test Rita Register"}
		)
		self.assertEqual(
			[(row.person, row.attendee_name, row.selection) for row in sign_up.attendees],
			[(None, "_Test Rita Register", "_Test Adult"), (None, "_Test Tim Typed", "_Test Child")],
		)

	def test_the_choices_offer_the_selections_of_an_open_function_only(self):
		frappe.get_doc(
			{
				"doctype": "Function Sign-Up Selection",
				"parent": self.function,
				"parenttype": "Function",
				"parentfield": "selections",
				"selection": "_Test Adult",
				"price": 0,
			}
		).insert(ignore_permissions=True)
		self.assertEqual([row["selection"] for row in self.choices()["selections"]], ["_Test Adult"])

		with self.assertRaises(frappe.PermissionError):
			self.choices(function=self.members_only)

	def test_the_choices_say_when_the_function_is_freely_given(self):
		self.assertFalse(self.choices()["freely_given"])
		frappe.get_doc(
			{
				"doctype": "Function Sign-Up Discount",
				"parent": self.function,
				"parenttype": "Function",
				"parentfield": "discounts",
				"kind": "Freely Given",
				"percent": 100,
			}
		).insert(ignore_permissions=True)
		self.assertTrue(self.choices()["freely_given"])

	def test_the_page_a_guest_gets_holds_no_household_name_after_a_member_opened_it(self):
		frappe.set_user(self.user)
		set_request(method="GET", path=ROUTE, query_string=f"church={self.church}&function={self.function}")
		frappe.local.form_dict = frappe._dict(church=self.church, function=self.function)
		self.assertIn("register-attendees", get_response(ROUTE).get_data(as_text=True))

		html = self.serve(function=self.function)
		for person in (self.spouse, self.child):
			self.assertNotIn(person.full_name, html)
			self.assertNotIn(person.name, html)
