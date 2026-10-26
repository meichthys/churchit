# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json

import frappe
from frappe.utils import set_request
from frappe.website.doctype.web_form.web_form import accept
from frappe.website.serve import get_response
from frappe.www.list import get_list_data

from churchit.church_foundations.church_access import set_user_church
from churchit.patches.v1_0 import add_room_request_to_portal
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)
from churchit.tests.test_questions import make_question_set


def make_room(room_name, church, **values):
	return ensure(
		"Room",
		{"room_name": room_name},
		{"room_name": room_name, "church": church, "is_bookable": 1, **values},
	)


class TestRoomRequest(RollbackEachTest):
	"""The members-only Room Request web form."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.gated_a = make_room("_Test A4 Gated Hall A", cls.branch_a, requires_approval=1)
		cls.closed_a = make_room("_Test A4 Closed Hall A", cls.branch_a, is_bookable=0)
		cls.room_b = make_room("_Test A4 Hall B", cls.branch_b)
		cls.shared_b = make_room("_Test A4 Shared Hall B", cls.branch_b, is_shared=1)
		cls.rooms = [cls.gated_a, cls.closed_a, cls.room_b, cls.shared_b]
		cls.member = ensure_user("_test_room_request_member@example.com", "RoomMember")
		cls.person = make_person("_Test Room", "Member", church=cls.branch_a, user=cls.member).name
		cls.other_member = ensure_user("_test_room_request_other@example.com", "RoomOther")
		cls.other_person = make_person("_Test Room", "Other", church=cls.branch_a, user=cls.other_member).name
		cls.stranger = make_person("_Test Room", "Stranger", church=cls.branch_a).name
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())
		self.addCleanup(setattr, frappe.local, "path", getattr(frappe.local, "path", None))
		self.addCleanup(setattr, frappe.flags, "in_web_form", False)

	def tearDown(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Room Booking", filters={"room": ["in", self.rooms]}, pluck="name"):
			frappe.delete_doc("Room Booking", name, force=True, ignore_permissions=True)
		super().tearDown()

	def request(self, room, hour=9, **values):
		data = {
			"doctype": "Room Booking",
			"room": room,
			"start_datetime": f"2036-04-04 {hour:02d}:00:00",
			"end_datetime": f"2036-04-04 {hour + 1:02d}:00:00",
			"purpose": "_Test A4 request",
			**values,
		}
		return accept("room-request", frappe.as_json(data))

	def room_options(self):
		frappe.local.form_dict = frappe._dict(is_new=1)
		frappe.local.path = "room-request/new"
		context = frappe._dict()
		frappe.get_doc("Web Form", "room-request").get_context(context)
		field = next(f for f in context.web_form_doc.web_form_fields if f.fieldname == "room")
		return {option["value"] for option in json.loads(field.options)}

	def test_a_members_request_on_a_gated_room_waits_with_their_own_person(self):
		frappe.set_user(self.member)
		booking = self.request(self.gated_a, requester=self.stranger, status="Approved")

		self.assertEqual(booking.status, "Requested")
		self.assertEqual(booking.requester, self.person)
		self.assertEqual(booking.church, self.branch_a)

	def test_a_members_own_save_takes_their_person_too(self):
		frappe.set_user(self.member)
		booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": self.gated_a,
				"requester": self.stranger,
				"purpose": "_Test A4 request",
				"start_datetime": "2036-04-05 09:00:00",
				"end_datetime": "2036-04-05 10:00:00",
			}
		).insert()
		self.assertEqual(booking.requester, self.person)

	def test_a_room_that_is_not_bookable_is_refused(self):
		frappe.set_user(self.member)
		with self.assertRaises(frappe.ValidationError):
			self.request(self.closed_a)

	def test_another_churchs_unshared_room_is_refused_and_a_shared_one_is_not(self):
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			self.request(self.room_b)
		self.assertEqual(self.request(self.shared_b).church, "")

	def test_a_member_can_neither_book_nor_read_equipment(self):
		asset = ensure(
			"Church Asset",
			{"title": "_Test A4 Projector"},
			{"title": "_Test A4 Projector", "church": self.branch_a, "is_bookable": 1},
		)
		frappe.set_user(self.member)

		self.assertFalse(frappe.has_permission("Church Asset", "select"))
		booking = {
			"doctype": "Room Booking",
			"assets": [{"asset": asset}],
			"purpose": "_Test A4 request",
			"start_datetime": "2036-04-06 09:00:00",
			"end_datetime": "2036-04-06 10:00:00",
		}
		with self.assertRaisesRegex(frappe.PermissionError, "equipment"):
			frappe.get_doc(booking).insert()
		with self.assertRaisesRegex(frappe.PermissionError, "equipment"):
			frappe.get_doc({**booking, "room": self.gated_a}).insert()

	def test_the_form_offers_only_the_bookable_rooms_of_the_members_church(self):
		frappe.set_user(self.member)
		options = self.room_options()
		self.assertIn(self.gated_a, options)
		self.assertIn(self.shared_b, options)
		self.assertNotIn(self.closed_a, options)
		self.assertNotIn(self.room_b, options)

	def test_a_room_with_a_required_question_is_not_offered_or_accepted(self):
		required = [{"label": "Expected attendance", "question_type": "Int", "is_required": 1}]
		optional = [{"label": "Catering", "question_type": "Data"}]
		asks = make_question_set("_Test A4 Required", required, church=self.branch_a).name
		may_ask = make_question_set("_Test A4 Optional", optional, church=self.branch_a).name
		frappe.db.set_value("Room", self.gated_a, "question_set", asks)
		frappe.db.set_value("Room", self.shared_b, "question_set", may_ask)

		frappe.set_user(self.member)
		options = self.room_options()
		self.assertNotIn(self.gated_a, options)
		self.assertIn(self.shared_b, options)
		with self.assertRaises(frappe.PermissionError):
			self.request(self.gated_a)
		self.assertEqual(self.request(self.shared_b).status, "Approved")

	def test_a_single_church_site_offers_every_bookable_room(self):
		force_single_church()
		frappe.set_user(self.member)
		options = self.room_options()
		self.assertTrue({self.gated_a, self.room_b, self.shared_b} <= options)
		self.assertNotIn(self.closed_a, options)
		self.assertEqual(self.request(self.room_b).requester, self.person)

	def test_a_login_with_no_person_is_offered_no_room_and_cannot_ask(self):
		frappe.set_user(ensure_user("_test_room_request_no_person@example.com", "RoomNoPerson"))
		self.assertEqual(self.room_options(), set())
		with self.assertRaises(frappe.ValidationError):
			self.request(self.gated_a)

	def test_the_list_shows_only_the_members_own_requests(self):
		frappe.set_user(self.member)
		mine = self.request(self.gated_a).name
		frappe.set_user(self.other_member)
		theirs = self.request(self.gated_a, hour=11).name

		listed = {row.name for row in get_list_data("Room Booking", web_form_name="room-request")}
		self.assertEqual(listed, {theirs})
		frappe.set_user(self.member)
		listed = {row.name for row in get_list_data("Room Booking", web_form_name="room-request")}
		self.assertEqual(listed, {mine})

	def book(self, hour, **values):
		return frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": self.gated_a,
				"purpose": "_Test A4 desk booking",
				"start_datetime": f"2036-04-07 {hour:02d}:00:00",
				"end_datetime": f"2036-04-07 {hour + 1:02d}:00:00",
				**values,
			}
		).insert(ignore_permissions=True)

	def test_the_list_shows_a_manager_only_their_own_requests(self):
		manager = ensure_user(
			"_test_room_request_lister@example.com", "RoomLister", roles=("Church Manager",)
		)
		set_user_church(manager, self.branch_a)
		own = make_person("_Test Room", "Lister", church=self.branch_a, user=manager).name
		mine = self.book(9, requester=own).name
		self.book(11, requester=self.stranger)

		frappe.set_user(manager)
		listed = {row.name for row in get_list_data("Room Booking", web_form_name="room-request")}
		self.assertEqual(listed, {mine})

	def test_a_staff_login_with_no_person_lists_no_blocked_time(self):
		self.book(9, status="Blocked")
		staff = ensure_user(
			"_test_room_request_blocker@example.com", "RoomBlocker", roles=("Church Manager",)
		)
		set_user_church(staff, self.branch_a)

		frappe.set_user(staff)
		self.assertEqual(get_list_data("Room Booking", web_form_name="room-request"), [])

	def test_a_manager_cannot_take_over_another_persons_booking_on_the_form(self):
		staff = ensure_user(
			"_test_room_request_manager@example.com", "RoomManager", roles=("Church Manager",)
		)
		set_user_church(staff, self.branch_a)
		own = make_person("_Test Room", "Staff", church=self.branch_a, user=staff).name
		desk_booking = frappe.get_doc(
			{
				"doctype": "Room Booking",
				"room": self.gated_a,
				"requester": self.stranger,
				"purpose": "_Test A4 desk booking",
				"start_datetime": "2036-04-06 09:00:00",
				"end_datetime": "2036-04-06 10:00:00",
			}
		).insert(ignore_permissions=True)
		frappe.set_user(staff)

		self.assertEqual(self.request(self.gated_a).requester, own)
		with self.assertRaises(frappe.PermissionError):
			self.request(self.gated_a, hour=13, name=desk_booking.name)
		self.assertEqual(frappe.db.get_value("Room Booking", desk_booking.name, "requester"), self.stranger)

	def test_a_guest_is_sent_to_login(self):
		"""Frappe sends a guest from the list to the new form, which it refuses with a Login button."""
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		frappe.set_user("Guest")
		path = "room-request"
		for _hop in range(3):
			frappe.local.form_dict = frappe._dict()
			set_request(method="GET", path=path)
			response = get_response(path)
			if response.status_code not in (301, 302):
				break
			path = response.headers["Location"].lstrip("/")

		self.assertEqual((path, response.status_code), ("room-request/new", 403))
		self.assertIn("/login?redirect-to=%2Froom-request%2Fnew", response.get_data(as_text=True))

	def test_the_patch_adds_book_a_room_to_the_portal_once(self):
		route = add_room_request_to_portal.ROUTE
		settings = frappe.get_doc("Portal Settings")
		settings.menu = [row for row in settings.menu if row.route != route]
		settings.save(ignore_permissions=True)

		add_room_request_to_portal.execute()
		add_room_request_to_portal.execute()

		rows = [row for row in frappe.get_doc("Portal Settings").menu if row.route == route]
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].title, rows[0].role), ("Book a Room", "Church User"))
