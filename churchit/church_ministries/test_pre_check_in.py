# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import formatdate, get_datetime, get_html_for_route
from frappe.utils.verified_command import get_signed_params

from churchit.church_foundations.church_access import set_user_church
from churchit.church_ministries import pre_check_in
from churchit.church_ministries.kiosk import KIOSK_ROLE, check_in_code
from churchit.church_people.test_household import link_user, make_household, set_adult_age
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_function,
	make_two_churches,
)
from churchit.www import household

DAY = "2031-05-01"


class TestPreCheckIn(RollbackEachTest):
	"""The Smiths: John and Jane (Adults), Tim (Child, 10) and Gran (Other Adult), all of church A."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		set_adult_age(18)
		cls.family, cls.father, cls.mother, cls.son, cls.grandmother = make_household("_Test Pre Check-In")
		frappe.db.set_value("Family", cls.family, "church", cls.branch_a)
		frappe.db.set_value("Person", {"family": cls.family}, "church", cls.branch_a)
		cls.father_user = link_user(cls.father, "_test_pre_check_in_father@example.com")
		cls.son_user = link_user(cls.son, "_test_pre_check_in_son@example.com")
		for user in (cls.father_user, cls.son_user):
			set_user_church(user, cls.branch_a)

		cls.volunteer = ensure_user(
			"_test_pre_check_in_station_a@example.com", "Station", ("Church Check-In",)
		)
		set_user_church(cls.volunteer, cls.branch_a)
		cls.volunteer_b = ensure_user(
			"_test_pre_check_in_station_b@example.com", "Station", ("Church Check-In",)
		)
		set_user_church(cls.volunteer_b, cls.branch_b)
		cls.kiosk = ensure_user("_test_pre_check_in_kiosk_a@example.com", "Kiosk", roles=(KIOSK_ROLE,))
		set_user_church(cls.kiosk, cls.branch_a)
		cls.kiosk_b = ensure_user("_test_pre_check_in_kiosk_b@example.com", "Kiosk", roles=(KIOSK_ROLE,))
		set_user_church(cls.kiosk_b, cls.branch_b)

		cls.self_type = ensure("Function Type", {"type": "_Test Pre Check-In Type"})
		frappe.db.set_value("Function Type", cls.self_type, "allow_self_check_in", 1)
		cls.function = cls.make_class("_Test Pre Check-In Class")

		frappe.get_single("Check-In Settings").save(ignore_permissions=True)
		frappe.db.set_single_value(
			"Check-In Settings",
			{"check_in_opens_minutes": 60, "capacity_mode": "Warn", "security_codes": 0},
		)

	@classmethod
	def make_class(cls, name, church=None, **values):
		return make_function(
			name,
			type=cls.self_type,
			church=church or cls.branch_a,
			start_date=DAY,
			start_time="10:00:00",
			end_time="11:00:00",
			**values,
		).name

	def setUp(self):
		super().setUp()
		self.at("09:30")
		self.enterContext(patch.object(frappe.db, "commit"))
		# The payload itself, so a test can scan it or change it.
		self.enterContext(patch.object(pre_check_in, "get_qr_code", side_effect=lambda value: value))

	def at(self, time):
		"""Run the rest of the test at *time* on DAY."""
		moment = get_datetime(f"{DAY} {time}")
		for target in ("check_in_limits.now_datetime", "pre_check_in.now_datetime"):
			self.enterContext(patch(f"churchit.church_ministries.{target}", return_value=moment))
		self.enterContext(patch("churchit.church_ministries.kiosk.today", return_value=DAY))

	def as_user(self, user, method, *args, **kwargs):
		frappe.set_user(user)
		try:
			return method(*args, **kwargs)
		finally:
			frappe.set_user("Administrator")

	def get_code(self, persons, function=None, user=None):
		result = self.as_user(
			user or self.father_user,
			pre_check_in.get_pre_check_in_code,
			function or self.function,
			frappe.as_json(persons),
		)
		return result["qr_code"]

	def scan(self, payload, user=None):
		return self.as_user(user or self.volunteer, pre_check_in.check_in, payload, print_tags=1)

	def scan_at_kiosk(self, payload, kiosk=None):
		return self.as_user(kiosk or self.kiosk, check_in_code, payload)

	def check_ins(self, function=None):
		return frappe.get_all(
			"Function Check-In", filters={"function": function or self.function}, pluck="person"
		)

	def test_an_adult_gets_a_signed_code_for_themselves_and_their_child(self):
		payload = self.get_code([self.father, self.son])

		params, signature = payload.split("&_signature=")
		self.assertEqual(get_signed_params(params), payload)
		self.assertEqual(pre_check_in.read_payload(payload), (self.function, [self.father, self.son]))

	def test_a_person_the_member_cannot_write_is_refused(self):
		for persons in ([self.father, self.grandmother], [self.mother]):
			self.assertRaises(frappe.PermissionError, self.get_code, persons)
		self.assertRaises(frappe.PermissionError, self.get_code, [self.father], user=self.son_user)
		self.assertRaises(frappe.ValidationError, self.get_code, [])

	def test_a_function_whose_type_does_not_allow_self_check_in_is_refused(self):
		staffed = make_function(
			"_Test Pre Check-In Staffed", church=self.branch_a, start_date=DAY, start_time="10:00"
		).name
		self.assertRaises(frappe.PermissionError, self.get_code, [self.son], staffed)

	def test_a_function_of_another_church_or_outside_its_window_is_refused(self):
		other = self.make_class("_Test Pre Check-In Other", church=self.branch_b)
		self.assertRaises(frappe.PermissionError, self.get_code, [self.son], other)

		self.at("08:59")
		self.assertRaises(frappe.PermissionError, self.get_code, [self.son])

	def test_a_child_outside_the_bounds_is_refused(self):
		toddlers = self.make_class("_Test Pre Check-In Toddlers", max_age=3)
		self.assertRaises(frappe.ValidationError, self.get_code, [self.son], toddlers)

	def test_a_station_scan_checks_the_people_in_and_prints_their_tags(self):
		result = self.scan(self.get_code([self.father, self.son]))

		self.assertCountEqual(self.check_ins(), [self.father, self.son])
		self.assertEqual(result["function_name"], "_Test Pre Check-In Class")
		self.assertEqual(len(result["new"]), 2)
		self.assertEqual(result["print"]["count"], 2)
		self.assertEqual(
			frappe.db.get_value("Function Check-In", result["new"][0], "check_in_kind"), "Regular"
		)

	def test_a_second_scan_of_one_payload_prints_nothing(self):
		payload = self.get_code([self.son])
		self.scan(payload)

		result = self.scan(payload)

		self.assertEqual(result["new"], [])
		self.assertNotIn("print", result)
		self.assertIsNone(self.scan_at_kiosk(payload)["print"])
		self.assertEqual(self.check_ins(), [self.son])

	def test_a_changed_payload_creates_and_prints_nothing(self):
		payload = self.get_code([self.son])
		changed = (
			payload.replace(self.son, self.grandmother),
			payload[:-1] + ("0" if payload[-1] != "0" else "1"),
			payload.split("&_signature=")[0],
			payload + "é",
			"f=" + self.function,
			get_signed_params({"email": "x", "f": self.function, "p": self.son, "u": "203105011100"}),
			get_signed_params({"f": self.function, "p": self.son, "u": "203105011100", "x": "1"}),
		)
		for scanned in changed:
			self.assertRaises(frappe.PermissionError, self.scan, scanned)
			self.assertRaises(frappe.PermissionError, self.scan_at_kiosk, scanned)
		self.assertEqual(self.check_ins(), [])

	def test_an_expired_payload_or_a_closed_window_creates_nothing(self):
		expired = get_signed_params({"f": self.function, "p": self.son, "u": "20310501092959"})
		self.assertRaises(frappe.PermissionError, self.scan, expired)

		payload = self.get_code([self.son])
		frappe.db.set_value("Function", self.function, "start_time", "10:45:00")
		self.assertRaises(frappe.PermissionError, self.scan, payload)
		self.assertRaises(frappe.PermissionError, self.scan_at_kiosk, payload)

		frappe.db.set_value("Function", self.function, "start_time", "10:00:00")
		self.at("11:01")
		self.assertRaises(frappe.PermissionError, self.scan, payload)
		self.assertEqual(self.check_ins(), [])

	def test_the_kiosk_checks_in_only_at_its_own_churchs_self_check_in_functions(self):
		payload = self.get_code([self.son])
		self.assertRaises(frappe.PermissionError, self.scan_at_kiosk, payload, self.kiosk_b)

		frappe.db.set_value("Function Type", self.self_type, "allow_self_check_in", 0)
		self.assertRaises(frappe.PermissionError, self.scan_at_kiosk, payload)
		frappe.db.set_value("Function Type", self.self_type, "allow_self_check_in", 1)
		self.assertEqual(self.check_ins(), [])

		result = self.scan_at_kiosk(payload)
		self.assertEqual(result["print"]["count"], 1)
		self.assertEqual(self.check_ins(), [self.son])

	def test_a_code_works_until_the_last_second_of_the_function(self):
		frappe.db.set_value("Function", self.function, "end_time", None)
		payload = self.get_code([self.son])

		self.at("23:59:30")
		self.assertEqual(len(self.scan(payload)["new"]), 1)

	def test_a_code_for_a_function_that_ends_on_a_later_day_shows_the_date(self):
		frappe.db.set_value("Function", self.function, "end_date", "2031-05-03")
		result = self.as_user(
			self.father_user, pre_check_in.get_pre_check_in_code, self.function, frappe.as_json([self.son])
		)
		self.assertIn(formatdate("2031-05-03"), result["valid_until"])

	def test_only_a_station_that_reads_the_function_may_scan(self):
		payload = self.get_code([self.son])
		self.assertRaises(frappe.PermissionError, self.scan, payload, self.volunteer_b)
		self.assertRaises(frappe.PermissionError, self.scan, payload, self.father_user)
		self.assertRaises(frappe.PermissionError, self.scan_at_kiosk, payload, self.volunteer)
		self.assertEqual(self.check_ins(), [])

	def test_the_household_page_offers_the_open_functions_to_the_people_the_member_may_write(self):
		other = self.make_class("_Test Pre Check-In Other", church=self.branch_b)
		frappe.set_user(self.father_user)
		context = frappe._dict()
		household.get_context(context)

		self.assertEqual([row.name for row in context.check_in_functions], [self.function])
		self.assertNotIn(other, [row.name for row in context.check_in_functions])
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		html = get_html_for_route("household")
		self.assertIn('id="pre-check-in"', html)
		self.assertIn(f'value="{self.son}"', html)
		self.assertNotIn(f'value="{self.mother}"', html)

		self.at("08:59")
		household.get_context(context)
		self.assertEqual(context.check_in_functions, [])

	def test_single_church_mode_still_offers_and_scans(self):
		force_single_church()
		result = self.scan(self.get_code([self.son]))
		self.assertEqual(len(result["new"]), 1)
