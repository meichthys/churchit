# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.form.load import get_docinfo

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people.history import get_timeline_content
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

EVERY_KIND = ("Visit", "Care Request", "_Test Baptism", "Transfer In", "Connection Card")


def make_care_request(person):
	frappe.get_doc(
		{
			"doctype": "Care Request",
			"person": person,
			"category": ensure("Care Request Type", {"type": "_Test Meals"}),
			"description": "_Test private need",
		}
	).insert(ignore_permissions=True)


def add_history(person, church=None):
	"""A visit, a care request, a transfer, a connection card and dated life events about *person*."""
	church = {"church": church} if church else {}
	frappe.get_doc(
		{
			"doctype": "Visitation Log",
			"person": person.name,
			"visit_type": ensure("Visit Type", {"type": "_Test Hospital"}),
			"visit_date": "2026-03-02",
			"visited_by": make_person("_Test Visiting", "Pastor").name,
			"status": "Completed",
		}
	).insert(ignore_permissions=True)
	make_care_request(person.name)
	frappe.get_doc(
		{
			"doctype": "Member Transfer",
			"person": person.name,
			"direction": "In",
			"other_church": "<b>_Test Grace</b>",
			"status": "Requested",
			**church,
		}
	).insert(ignore_permissions=True)
	for status in ("New", "Spam"):
		frappe.get_doc(
			{
				"doctype": "Connection Card",
				"first_name": "_Test Card",
				"last_name": status,
				"person": person.name,
				"status": status,
				**church,
			}
		).insert(ignore_permissions=True)
	ensure("Life Event Type", {"type": "_Test Baptism"})
	ensure("Life Event Type", {"type": "_Test Wedding"})
	person.append(
		"life_events", {"event_type": "_Test Baptism", "date": "2001-04-15", "location": "_Test River"}
	)
	person.append("life_events", {"event_type": "_Test Wedding", "date": "1900-06-01", "year_unknown": 1})
	person.append("life_events", {"event_type": "_Test Wedding"})
	person.save(ignore_permissions=True)


def raise_permission_level(case, doctype, fieldname):
	make_property_setter(doctype, fieldname, "permlevel", 1, "Int")
	frappe.clear_cache(doctype=doctype)
	case.addCleanup(frappe.clear_cache, doctype=doctype)


def get_cards(user, person):
	frappe.set_user(user)
	try:
		return get_timeline_content("Person", person)
	finally:
		frappe.set_user("Administrator")


def timeline_text(user, person):
	return "".join(card["content"] for card in get_cards(user, person))


class TestPersonHistory(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.manager = ensure_user("_test_history_manager@example.com", "Manager", ["Church Manager"])
		cls.staff = ensure_user("_test_history_staff@example.com", "Staff", ["Church Staff"])
		cls.check_in = ensure_user("_test_history_check_in@example.com", "Check In", ["Church Check-In"])
		person = make_person("_Test History", "Person")
		add_history(person)
		cls.person = person.name

	def test_a_manager_sees_every_kind_of_record(self):
		text = timeline_text(self.manager, self.person)

		for heading in EVERY_KIND:
			self.assertIn(heading, text)
		self.assertIn("By _Test Visiting Pastor", text)
		self.assertNotIn("_Test private need", text)

	def test_staff_see_only_the_records_their_roles_read(self):
		frappe.set_user(self.staff)
		make_care_request(self.person)
		frappe.set_user("Administrator")

		text = timeline_text(self.staff, self.person)

		self.assertEqual(text.count("Care Request"), 1, "Church Staff read only the care requests they added")
		self.assertIn("Connection Card", text)
		self.assertIn("_Test Baptism", text)
		self.assertNotIn("Visit", text)
		self.assertNotIn("Transfer", text)

	def test_a_role_that_cannot_read_care_sees_only_life_events(self):
		cards = get_cards(self.check_in, self.person)

		self.assertEqual([card["icon"] for card in cards], ["calendar-heart"])

	def test_life_events_without_a_full_date_and_spam_cards_stay_off(self):
		text = timeline_text(self.manager, self.person)

		self.assertNotIn("_Test Wedding", text)
		self.assertEqual(text.count("Connection Card"), 1)
		self.assertNotIn("Spam", text)

	def test_typed_text_is_escaped(self):
		text = timeline_text(self.manager, self.person)

		self.assertIn("&lt;b&gt;_Test Grace&lt;/b&gt;", text)
		self.assertNotIn("<b>_Test Grace", text)

	def test_a_field_above_the_readers_permission_level_is_left_out(self):
		raise_permission_level(self, "Visitation Log", "visited_by")

		text = timeline_text(self.manager, self.person)

		self.assertIn("Visit", text)
		self.assertNotIn("_Test Visiting Pastor", text)

	def test_life_events_stay_off_when_the_reader_may_not_read_the_table(self):
		raise_permission_level(self, "Person", "life_events")

		text = timeline_text(self.staff, self.person)

		self.assertNotIn("_Test Baptism", text)
		self.assertIn("Connection Card", text)
		self.assertIn("_Test Baptism", timeline_text(self.manager, self.person))

	def test_a_date_above_the_readers_permission_level_hides_those_records_without_an_error(self):
		raise_permission_level(self, "Visitation Log", "visit_date")

		text = timeline_text(self.manager, self.person)

		self.assertNotIn("Visit", text)
		self.assertIn("Care Request", text)

	def test_the_person_form_loads_the_cards(self):
		frappe.set_user(self.manager)
		get_docinfo(doctype="Person", name=self.person)
		frappe.set_user("Administrator")

		content = "".join(card["content"] for card in frappe.response.docinfo.additional_timeline_content)
		self.assertIn("Care Request", content)

	def test_no_record_read_has_a_permission_hook_that_get_list_would_skip(self):
		with patch.object(frappe, "get_list", wraps=frappe.get_list) as get_list:
			get_timeline_content("Person", self.person)
		read = {call.args[0] for call in get_list.call_args_list}

		self.assertEqual(read & set(frappe.get_hooks("has_permission")), set())
		self.assertEqual(read & {"Counseling Case", "Background Check"}, set())


class TestPersonHistoryAcrossChurches(RollbackEachTest):
	def setUp(self):
		super().setUp()
		_root, branch_a, branch_b = make_two_churches()
		self.manager_a = ensure_user("_test_history_manager_a@example.com", "Manager A", ["Church Manager"])
		self.manager_b = ensure_user("_test_history_manager_b@example.com", "Manager B", ["Church Manager"])
		set_user_church(self.manager_a, branch_a)
		set_user_church(self.manager_b, branch_b)
		person = make_person("_Test History", "Elsewhere", church=branch_b)
		add_history(person, church=branch_b)
		self.person = person.name

	def test_a_branch_user_sees_only_the_life_events_of_another_churchs_person(self):
		cards = get_cards(self.manager_a, self.person)

		self.assertEqual([card["icon"] for card in cards], ["calendar-heart"])

	def test_the_persons_own_church_sees_every_kind_of_record(self):
		text = timeline_text(self.manager_b, self.person)

		for heading in EVERY_KIND:
			self.assertIn(heading, text)
