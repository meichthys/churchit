# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_to_date, getdate, now_datetime

from churchit.church_ministries.doctype.function_sign_up.function_sign_up import FunctionSignUp
from churchit.portal import events
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_function,
	make_person,
	make_two_churches,
)
from churchit.tests.test_questions import make_question_set

NOTIFY = "churchit.portal.realtime.frappe.publish_realtime"


def make_sign_up(function: str, person: str, owner: str | None = None, **values) -> FunctionSignUp:
	"""A sign-up saved by code, the way staff or the register page make one."""
	user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		doc = frappe.get_doc(
			{"doctype": "Function Sign-Up", "function": function, "person": person, "attending": 1, **values}
		).insert(ignore_permissions=True)
		if owner:
			doc.db_set("owner", owner)
		return doc
	finally:
		frappe.set_user(user)


def portal_calls(publish) -> list:
	"""The member app events among the realtime messages a mock saw."""
	return [call for call in publish.call_args_list if call.args[0] == "churchit_portal"]


class EventsTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.email = ensure_user("_test_events_member@example.com", "EventsMember")
		cls.other_email = ensure_user("_test_events_other@example.com", "EventsOther")
		cls.person = make_person("_Test Events", "Member", user=cls.email).name
		cls.other = make_person("_Test Events", "Other", user=cls.other_email).name

	def setUp(self):
		super().setUp()
		force_single_church()
		frappe.local.form_dict = frappe._dict()
		frappe.db.set_single_value("Portal Settings", "members_can_change_attendance", 0)
		frappe.set_user(self.email)

	def open_function(self, name="_Test Open Function", **values):
		values.setdefault("start_date", add_days(getdate(), 10))
		return make_function(name, allow_sign_ups=1, **values).name

	def names(self, rows: list[dict], key="name") -> list[str]:
		return [row[key] for row in rows]


class TestAttendance(EventsTestCase):
	def make_attended(self, name, days, person, attendance_type="Confirmed"):
		function = make_function(
			name,
			start_date=add_days(getdate(), days),
			attendance=[{"person": person, "attendance_type": attendance_type}],
		)
		return function.name

	def test_a_member_sees_their_own_past_attendance_only(self):
		mine = self.make_attended("_Test Events Mine", -3, self.person)
		theirs = self.make_attended("_Test Events Theirs", -3, self.other)

		past = events.get_attendance()["past"]

		self.assertIn(mine, self.names(past, "function"))
		self.assertNotIn(theirs, self.names(past, "function"))

	def test_a_row_is_changeable_only_when_portal_settings_allow_it_and_not_checked_in(self):
		confirmed = self.make_attended("_Test Events Confirmed", -2, self.person)
		checked_in = self.make_attended("_Test Events In", -4, self.person, "Checked-In")

		self.assertFalse(any(row["is_changeable"] for row in events.get_attendance()["past"]))

		frappe.db.set_single_value("Portal Settings", "members_can_change_attendance", 1)
		result = events.get_attendance()
		rows = {row["function"]: row for row in result["past"]}

		self.assertEqual(result["choices"], ["Confirmed", "Absent"])
		self.assertTrue(rows[confirmed]["is_changeable"])
		self.assertFalse(rows[checked_in]["is_changeable"])

	def test_upcoming_lists_live_sign_ups_with_the_sign_up_to_open(self):
		function = self.open_function()
		sign_up = make_sign_up(function, self.person)

		upcoming = events.get_attendance()["upcoming"]

		self.assertEqual(upcoming[0]["function"], function)
		self.assertEqual(upcoming[0]["sign_up"], sign_up.name)
		self.assertEqual(upcoming[0]["status"], "Confirmed")

	def test_a_guest_and_a_login_without_a_person_are_refused(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			events.get_attendance()

		frappe.set_user(ensure_user("_test_events_nobody@example.com", "Nobody"))
		with self.assertRaises(frappe.PermissionError):
			events.get_attendance()

	def test_a_switched_off_page_is_refused(self):
		with patch("churchit.portal.access.get_hidden_pages", return_value={"attendance"}):
			with self.assertRaises(frappe.PermissionError):
				events.get_attendance()


class TestOpenFunctions(EventsTestCase):
	def test_a_simple_open_function_signs_up_in_the_app(self):
		function = self.open_function()

		rows = {row["name"]: row for row in events.get_open_functions()["items"]}

		self.assertEqual(rows[function]["signs_up_in"], "app")
		self.assertEqual(rows[function]["date_display"], frappe.utils.formatdate(add_days(getdate(), 10)))

	def test_a_function_with_a_question_set_goes_to_register(self):
		question_set = make_question_set("_Test Events Questions")
		function = self.open_function("_Test Events Questions", question_set=question_set.name)

		rows = {row["name"]: row for row in events.get_open_functions()["items"]}

		self.assertEqual(rows[function]["signs_up_in"], "register")

	def test_a_function_outside_its_window_is_not_listed(self):
		closed = self.open_function(
			"_Test Events Closed", sign_ups_close_on=add_to_date(now_datetime(), days=-1)
		)
		not_yet = self.open_function(
			"_Test Events Later", sign_ups_open_on=add_to_date(now_datetime(), days=1)
		)

		listed = self.names(events.get_open_functions()["items"])

		self.assertNotIn(closed, listed)
		self.assertNotIn(not_yet, listed)

	def test_a_function_the_member_already_signed_up_for_is_not_listed(self):
		function = self.open_function()
		make_sign_up(function, self.person)

		self.assertNotIn(function, self.names(events.get_open_functions()["items"]))

	def test_another_churchs_function_is_not_listed_or_signed_up_for(self):
		frappe.set_user("Administrator")
		root, church_a, church_b = make_two_churches()
		frappe.set_user(self.email)
		frappe.db.set_value("Person", self.person, "church", church_a)
		mine = self.open_function("_Test Events Mine", church=church_a)
		theirs = self.open_function("_Test Events Theirs", church=church_b)

		listed = self.names(events.get_open_functions()["items"])

		self.assertIn(mine, listed)
		self.assertNotIn(theirs, listed)
		with self.assertRaises(frappe.PermissionError):
			events.sign_up(theirs)

	def test_a_switched_off_page_is_refused(self):
		with patch("churchit.portal.access.get_hidden_pages", return_value={"function-sign-up"}):
			with self.assertRaises(frappe.PermissionError):
				events.get_open_functions()


class TestSignUp(EventsTestCase):
	def test_signing_up_saves_the_members_own_sign_up(self):
		function = self.open_function()

		result = events.sign_up(function, attending="true", notes="Bringing a friend")

		doc = frappe.get_doc("Function Sign-Up", result["name"])
		self.assertEqual(doc.person, self.person)
		self.assertEqual(doc.owner, self.email)
		self.assertEqual(doc.notes, "Bringing a friend")
		self.assertEqual(result["status"], "Confirmed")

	def test_a_person_the_browser_names_is_ignored(self):
		function = self.open_function()
		frappe.local.form_dict = frappe._dict(person=self.other)

		result = events.sign_up(function)

		self.assertEqual(frappe.db.get_value("Function Sign-Up", result["name"], "person"), self.person)

	def test_items_keep_only_the_quantity(self):
		item = frappe.get_doc({"doctype": "Sign-Up Item", "item": "_Test Events Drinks"}).insert(
			ignore_permissions=True
		)
		function = make_function(
			"_Test Events Items",
			allow_sign_ups=1,
			start_date=add_days(getdate(), 5),
			table_cxhh=[{"item": item.name, "quantity_needed": 6}],
		)

		result = events.sign_up(function.name, items=[{"item": item.name, "my_quantity": 2}])

		doc = frappe.get_doc("Function Sign-Up", result["name"])
		self.assertEqual([(row.item, row.my_quantity) for row in doc.table_iprj], [(item.name, 2)])

	def test_a_function_that_is_not_open_is_refused(self):
		function = make_function("_Test Events Not Open", start_date=add_days(getdate(), 5)).name

		with self.assertRaises(frappe.PermissionError):
			events.sign_up(function)

	def test_the_second_sign_up_for_one_function_is_refused(self):
		function = self.open_function()
		events.sign_up(function)

		with self.assertRaises(frappe.PermissionError):
			events.sign_up(function)

	def test_the_member_is_told_live(self):
		function = self.open_function()

		with patch(NOTIFY) as publish:
			result = events.sign_up(function)

		topics = {(call.args[1]["topic"], call.kwargs["user"]) for call in portal_calls(publish)}
		self.assertIn(("sign-ups", self.email), topics)
		self.assertIn(("attendance", self.email), topics)
		hints = {call.args[1]["topic"]: call.args[1]["name"] for call in portal_calls(publish)}
		self.assertEqual(hints["sign-ups"], result["name"])
		self.assertEqual(hints["attendance"], function)


class TestReadingSignUps(EventsTestCase):
	def test_the_list_holds_only_the_members_own_sign_ups(self):
		function = self.open_function()
		mine = make_sign_up(function, self.person, self.email)
		theirs = make_sign_up(function, self.other)

		items = events.get_sign_ups()["items"]

		self.assertIn(mine.name, self.names(items))
		self.assertNotIn(theirs.name, self.names(items))
		row = next(row for row in items if row["name"] == mine.name)
		self.assertTrue(row["can_cancel"])
		self.assertEqual(row["function_name"], "_Test Open Function")

	def test_another_members_sign_up_is_refused(self):
		theirs = make_sign_up(self.open_function(), self.other)

		with self.assertRaises(frappe.PermissionError):
			events.get_sign_up(theirs.name)

	def test_a_sign_up_shows_what_the_member_may_do(self):
		mine = make_sign_up(self.open_function(), self.person, self.email)

		detail = events.get_sign_up(mine.name)

		self.assertTrue(detail["can_edit"])
		self.assertTrue(detail["can_cancel"])
		self.assertEqual(detail["status"], "Confirmed")

	def test_a_sign_up_staff_made_cannot_be_changed(self):
		staff = make_sign_up(self.open_function(), self.person)

		detail = events.get_sign_up(staff.name)

		self.assertFalse(detail["can_edit"])
		self.assertFalse(detail["can_cancel"])


class TestChangingSignUps(EventsTestCase):
	def test_update_changes_attending_and_notes_but_not_the_function(self):
		function = self.open_function()
		sign_up = make_sign_up(function, self.person, self.email)
		elsewhere = self.open_function("_Test Events Elsewhere")
		frappe.local.form_dict = frappe._dict(function=elsewhere)

		events.update_sign_up(sign_up.name, attending="false", notes="Away")

		doc = frappe.get_doc("Function Sign-Up", sign_up.name)
		self.assertEqual((doc.function, doc.attending, doc.notes), (function, 0, "Away"))

	def test_another_members_sign_up_cannot_be_changed_or_cancelled(self):
		theirs = make_sign_up(self.open_function(), self.other, self.other_email)

		with self.assertRaises(frappe.PermissionError):
			events.update_sign_up(theirs.name, notes="Mine now")
		with self.assertRaises(frappe.PermissionError):
			events.cancel_sign_up(theirs.name)
		self.assertEqual(frappe.db.get_value("Function Sign-Up", theirs.name, "status"), "Confirmed")

	def test_cancel_cancels_and_the_member_cannot_edit_it_after(self):
		sign_up = make_sign_up(self.open_function(), self.person, self.email)

		with patch(NOTIFY) as publish:
			result = events.cancel_sign_up(sign_up.name)

		self.assertEqual(result["status"], "Cancelled")
		self.assertTrue(any(call.args[1]["topic"] == "sign-ups" for call in portal_calls(publish)))
		with self.assertRaises(frappe.PermissionError):
			events.update_sign_up(sign_up.name, notes="Again")
		self.assertFalse(events.get_sign_up(sign_up.name)["can_cancel"])

	def test_a_status_change_by_staff_tells_the_registrant(self):
		function = self.open_function(capacity=1)
		first = make_sign_up(function, self.other)
		second = make_sign_up(function, self.person)
		self.assertEqual(second.status, "Waitlisted")

		frappe.set_user("Administrator")
		with patch(NOTIFY) as publish:
			first.cancel_registration()

		users = {call.kwargs["user"] for call in portal_calls(publish) if call.args[1]["topic"] == "sign-ups"}
		self.assertIn(self.email, users)
		self.assertEqual(frappe.db.get_value("Function Sign-Up", second.name, "status"), "Confirmed")


class TestFixes(EventsTestCase):
	def test_the_detail_sends_the_stored_status_and_why_it_waits(self):
		function = self.open_function()
		sign_up = make_sign_up(function, self.person, self.email)
		frappe.db.set_value("Function Sign-Up", sign_up.name, "status", "Pending")

		with patch("frappe.translate.get_user_lang", return_value="de"):
			detail = events.get_sign_up(sign_up.name)

		self.assertEqual(detail["status"], "Pending")
		self.assertEqual(detail["waits_for"], "approval")

		frappe.db.set_value("Function Sign-Up", sign_up.name, "hold_expires_on", add_days(now_datetime(), 1))
		self.assertEqual(events.get_sign_up(sign_up.name)["waits_for"], "payment")

	def test_a_description_becomes_plain_text(self):
		text = events.to_plain_text('<p>Food &amp; drinks&nbsp;for "all"</p><p>Second</p>')

		self.assertEqual(text, 'Food & drinks for "all"\nSecond')

	def test_the_closing_time_has_no_seconds(self):
		self.assertNotIn(":00:00", events.format_closing("2031-01-02 23:59:00"))
		self.assertTrue(events.format_closing("2031-01-02 23:59:00").lower().endswith("11:59 pm"))

	def test_items_the_function_does_not_ask_for_are_refused(self):
		function = self.open_function()

		with self.assertRaises(frappe.ValidationError):
			events.sign_up(function, items=[{"item": "_Not On Function", "my_quantity": 9}])
		with self.assertRaises(frappe.ValidationError):
			events.sign_up(function, items='[{"my_quantity": 1}]')
		with self.assertRaises(frappe.ValidationError):
			events.sign_up(function, items='{"x": 1}')

	def test_the_item_total_leaves_out_the_members_own_rows(self):
		item = frappe.get_doc({"doctype": "Sign-Up Item", "item": "_Test Events Cookies"}).insert(
			ignore_permissions=True
		)
		function = make_function(
			"_Test Events Own Items",
			allow_sign_ups=1,
			start_date=add_days(getdate(), 5),
			table_cxhh=[{"item": item.name, "quantity_needed": 4}],
		)
		result = events.sign_up(function.name, items=[{"item": item.name, "my_quantity": 2}])

		detail = events.get_sign_up(result["name"])

		self.assertEqual(detail["items"][0]["quantity_signed_up"], 0)
		self.assertEqual(detail["items"][0]["my_quantity"], 2)

	def test_a_member_cannot_cancel_after_the_event_day(self):
		function = self.open_function("_Test Events Held", start_date=add_days(getdate(), -1))
		sign_up = make_sign_up(function, self.person, self.email)

		self.assertFalse(events.get_sign_up(sign_up.name)["can_cancel"])
		self.assertFalse(events.get_sign_ups()["items"][0]["can_cancel"])

	def test_the_attendance_hint_names_the_function(self):
		function = self.open_function(capacity=1)
		first = make_sign_up(function, self.other)

		with patch(NOTIFY) as publish:
			frappe.set_user("Administrator")
			first.cancel_registration()

		hints = [call.args[1] for call in portal_calls(publish) if call.args[1]["topic"] == "attendance"]
		self.assertTrue(hints)
		self.assertTrue(all(hint["name"] == function for hint in hints))

	def test_another_churchs_sign_up_is_refused_in_the_app(self):
		frappe.set_user("Administrator")
		root, church_a, church_b = make_two_churches()
		frappe.db.set_value("Person", self.person, "church", church_a)
		function = self.open_function("_Test Events Church B", church=church_b)
		theirs = make_sign_up(function, self.other, self.other_email)
		frappe.set_user(self.email)

		for call in (
			lambda: events.get_sign_up(theirs.name),
			lambda: events.update_sign_up(theirs.name, notes="x"),
			lambda: events.cancel_sign_up(theirs.name),
		):
			with self.assertRaises(frappe.PermissionError):
				call()

	def test_a_switched_off_page_refuses_every_sign_up_endpoint(self):
		mine = make_sign_up(self.open_function(), self.person, self.email)
		calls = (
			lambda: events.get_sign_ups(),
			lambda: events.get_sign_up(mine.name),
			lambda: events.sign_up("x"),
			lambda: events.update_sign_up(mine.name),
			lambda: events.cancel_sign_up(mine.name),
		)

		with patch("churchit.portal.access.get_hidden_pages", return_value={"function-sign-up"}):
			for call in calls:
				with self.assertRaises(frappe.PermissionError):
					call()
