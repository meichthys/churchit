# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The people reads of AI apps answer as the caller: their churches, their fields, their records."""

import json
from unittest.mock import patch
from urllib.parse import parse_qsl, urlparse

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.reportview import save_report
from frappe.utils import add_days, today

from churchit.church_foundations.church_access import set_user_church
from churchit.church_people import ai, smart_lists
from churchit.church_people.doctype.follow_up_card.test_follow_up_card import make_workflow
from churchit.church_people.followup import add_card
from churchit.church_people.test_notes import make_category, make_note
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_smart_list,
	make_two_churches,
	pop_logs,
)

LAST_NAME = "_Test AI People"
WINDOW = {"start": "2031-03-02", "end": "2031-03-08"}


def set_ai(enabled: int) -> None:
	frappe.db.set_single_value("Church AI Settings", "enabled", enabled)


def as_user(user, function, *args, **kwargs):
	frappe.set_user(user)
	try:
		return function(*args, **kwargs)
	finally:
		frappe.set_user("Administrator")


def raise_permission_level(case, doctype, fieldname, level=1):
	make_property_setter(doctype, fieldname, "permlevel", level, "Int")
	frappe.clear_cache(doctype=doctype)
	case.addCleanup(frappe.clear_cache, doctype=doctype)


def names(page):
	return {row["name"] for row in page["rows"]}


def filters_from_url(url):
	"""The filters the desk's report view reads from *url* (list_view.js parse_filters_from_route_options)."""
	filters = []
	for key, value in parse_qsl(urlparse(url).query):
		doctype, field = key.split(".") if "." in key else ("Person", key)
		filters.append([doctype, field, *json.loads(value)])
	return filters


class AITestCase(RollbackEachTest):
	"""Two branches; a Church Manager and Church Staff of branch A, and a portal member."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.manager = ensure_user("_test_ai_people_manager@example.com", "AI Manager", ["Church Manager"])
		cls.staff = ensure_user("_test_ai_people_staff@example.com", "AI Staff", ["Church Staff"])
		cls.member = ensure_user("_test_ai_people_member@example.com", "AI Member", ["Church User"])
		for user in (cls.manager, cls.staff):
			set_user_church(user, cls.branch_a)
		cls.member_type = ensure("Membership Type", {"type": "Member"})
		cls.active = ensure("Member Status", {"status": "Active"})
		ensure("Life Event Type", {"type": "Birth"})

	def setUp(self):
		super().setUp()
		set_ai(1)

	def make_pair(self, first_name, **values):
		"""The names of a person of branch A and one of branch B, both with *values*."""
		return tuple(
			make_person(f"{first_name} {branch}", LAST_NAME, church=church, **values).name
			for branch, church in (("A", self.branch_a), ("B", self.branch_b))
		)


class TestTheRefusals(AITestCase):
	READS = (
		(ai.get_smart_list_url, ([["last_name", "=", LAST_NAME]],)),
		(ai.get_smart_list_people, ("First-Time Visitors",)),
		(ai.first_time_guests_without_follow_up, ()),
		(ai.people_not_seen, ()),
		(ai.birthdays_and_anniversaries, ()),
		(ai.groups_needing_attention, ()),
	)

	def test_a_portal_member_is_refused_every_read(self):
		for function, args in self.READS:
			with self.subTest(function.__name__):
				self.assertRaises(frappe.PermissionError, as_user, self.member, function, *args)

	def test_every_read_is_refused_while_ai_is_off(self):
		set_ai(0)
		for function, args in self.READS:
			with self.subTest(function.__name__):
				self.assertRaises(frappe.PermissionError, as_user, self.manager, function, *args)

	def test_a_briefing_refuses_a_portal_member_and_ai_off(self):
		person = make_person("Briefed", LAST_NAME, church=self.branch_a).name
		group = frappe.get_doc(
			{"doctype": "Group", "group_name": "_Test AI Refused", "church": self.branch_a}
		)
		briefings = ((ai.get_person_briefing, person), (ai.get_group_briefing, group.insert().name))
		for function, name in briefings:
			self.assertRaises(frappe.PermissionError, as_user, self.member, function, name)
		set_ai(0)
		for function, name in briefings:
			self.assertRaises(frappe.PermissionError, as_user, self.manager, function, name)


class TestSmartListUrl(AITestCase):
	def test_the_link_and_count_cover_the_callers_churches_only(self):
		mine, theirs = self.make_pair("Guest")
		for person in (mine, theirs):
			frappe.db.set_value("Person", person, "first_attended_on", today())
		filters = [
			["last_name", "=", LAST_NAME],
			["first_attended_on", "Timespan", "last 30 days"],
			["Person Group", "group", "is", "not set"],
		]

		result = as_user(self.manager, ai.get_smart_list_url, filters, ["last_attended_on"])

		self.assertEqual(result["count"], 1)
		self.assertIn("Only the churches you may see.", result["explanation"])
		self.assertIn("Last Attended", result["explanation"])
		self.assertIn(["Person Group", "group", "is", "not set"], filters_from_url(result["url"]))
		self.assertIn(["Person", "church", "in", [self.branch_a, ""]], filters_from_url(result["url"]))

	def test_a_list_saved_from_the_link_is_a_smart_list_of_the_same_people(self):
		mine, _theirs = self.make_pair("Saved")
		url = as_user(self.manager, ai.get_smart_list_url, [["last_name", "=", LAST_NAME]])["url"]

		report = save_report("_Test AI Saved List", "Person", json.dumps({"filters": filters_from_url(url)}))

		self.assertTrue(smart_lists.is_smart_list(report))
		self.assertEqual(smart_lists.get_people(report, None), [mine])

	def test_the_list_holds_living_people_unless_a_filter_names_is_deceased(self):
		make_person("Living", LAST_NAME, church=self.branch_a)
		died = make_person("Died", LAST_NAME, church=self.branch_a).name
		frappe.db.set_value("Person", died, "is_deceased", 1)

		result = as_user(self.manager, ai.get_smart_list_url, [["last_name", "=", LAST_NAME]])
		self.assertEqual(result["count"], 1)
		self.assertIn("Living people only.", result["explanation"])

		filters = [["last_name", "=", LAST_NAME], ["is_deceased", "=", 1]]
		result = as_user(self.manager, ai.get_smart_list_url, filters)
		self.assertEqual(result["count"], 1)
		self.assertNotIn("Living people only.", result["explanation"])

	def test_staff_may_not_filter_or_show_giving(self):
		for filters, fields in (([["is_lapsed_giver", "=", 1]], None), ([], ["last_gift_on"])):
			with self.subTest(filters=filters, fields=fields):
				self.assertRaises(
					frappe.PermissionError, as_user, self.staff, ai.get_smart_list_url, filters, fields
				)

	def test_a_finance_user_counts_the_lapsed_givers_of_their_churches_only(self):
		finance = ensure_user(
			"_test_ai_people_finance@example.com", "AI Finance", ["Church Staff", "Church Finance"]
		)
		set_user_church(finance, self.branch_a)
		for person in self.make_pair("Lapsed"):
			frappe.db.set_value("Person", person, "is_lapsed_giver", 1)

		filters = [["is_lapsed_giver", "=", 1], ["last_name", "=", LAST_NAME]]
		self.assertEqual(as_user(finance, ai.get_smart_list_url, filters)["count"], 1)

	def test_a_table_the_caller_may_not_read_is_refused(self):
		raise_permission_level(self, "Person", "groups", 2)

		filters = [["Person Group", "group", "is", "set"]]
		self.assertRaises(frappe.PermissionError, as_user, self.staff, ai.get_smart_list_url, filters)
		self.assertIn("count", as_user(self.manager, ai.get_smart_list_url, filters))

	def test_filters_frappe_cannot_run_are_refused(self):
		for filters in (
			[["no_such_field", "=", 1]],
			[["Group", "group_name", "=", "x"]],
			[["full_name", "resembles", "x"]],
			[["first_attended_on", "Timespan", "the age of Noah"]],
			[["last_name"]],
			[["last_name", "=", str(number)] for number in range(ai.MAX_FILTERS + 1)],
		):
			with self.subTest(filters=filters):
				self.assertRaises(
					frappe.ValidationError, as_user, self.manager, ai.get_smart_list_url, filters
				)


class TestSmartListPeople(AITestCase):
	def test_the_caller_gets_the_names_of_their_churches_people_only(self):
		mine, _theirs = self.make_pair("Listed")
		report = make_smart_list("_Test AI List", filters=(("Person", "last_name", "=", LAST_NAME),)).name

		rows = as_user(self.manager, ai.get_smart_list_people, report)

		self.assertEqual([row.name for row in rows], [mine])
		self.assertEqual(set(rows[0]), {"name", "full_name"})

	def test_a_list_saved_with_the_old_fifth_filter_element_is_read(self):
		mine, _theirs = self.make_pair("Older")
		older = (("Person", "last_name", "=", LAST_NAME, False),)
		report = make_smart_list("_Test AI Older List", filters=older).name

		rows = as_user(self.manager, ai.get_smart_list_people, report)

		self.assertEqual([row.name for row in rows], [mine])

	def test_lists_the_caller_may_not_run_are_refused(self):
		not_a_list = make_smart_list("_Test AI Family List", ref_doctype="Family").name
		giving = make_smart_list(
			"_Test AI Giving List", filters=(("Person", "is_lapsed_giver", "=", 1),)
		).name

		self.assertRaises(frappe.ValidationError, as_user, self.staff, ai.get_smart_list_people, not_a_list)
		self.assertRaises(frappe.PermissionError, as_user, self.staff, ai.get_smart_list_people, giving)
		self.assertRaises(
			frappe.PermissionError, as_user, self.staff, ai.get_smart_list_people, "Members Not Seen Lately"
		)
		self.assertEqual(as_user(self.manager, ai.get_smart_list_people, giving), [])

	def test_at_most_the_cap_comes_back(self):
		self.make_pair("Capped")
		make_person("Capped Again", LAST_NAME, church=self.branch_a)
		report = make_smart_list(
			"_Test AI Capped List", filters=(("Person", "last_name", "=", LAST_NAME),)
		).name

		with patch.object(ai, "MAX_PEOPLE", 1):
			self.assertEqual(len(as_user(self.manager, ai.get_smart_list_people, report, 100)), 1)


class TestOfficeReads(AITestCase):
	def test_first_time_guests_without_a_follow_up_card_of_the_callers_churches(self):
		mine, theirs = self.make_pair("Guest")
		followed = make_person("Followed", LAST_NAME, church=self.branch_a).name
		for person in (mine, theirs, followed):
			frappe.db.set_value("Person", person, "first_attended_on", today())
		add_card(followed, make_workflow("_Test AI Welcome", [("Call", None, 2)], church=self.branch_a).name)

		found = names(as_user(self.manager, ai.first_time_guests_without_follow_up, 7))

		self.assertIn(mine, found)
		self.assertNotIn(theirs, found)
		self.assertNotIn(followed, found)

	def test_people_not_seen_of_the_callers_churches_with_the_full_list(self):
		member = {"membership": self.member_type, "membership_status": self.active}
		mine, theirs = self.make_pair("Away", **member)
		recent = make_person("Recent", LAST_NAME, church=self.branch_a, **member).name
		for person, days in ((mine, 70), (theirs, 70), (recent, 7)):
			frappe.db.set_value("Person", person, "last_attended_on", add_days(today(), -days))

		page = as_user(self.manager, ai.people_not_seen, 8)

		self.assertIn(mine, names(page))
		self.assertNotIn(theirs, names(page))
		self.assertNotIn(recent, names(page))
		self.assertGreaterEqual(page["total"], 1)
		self.assertIn(["Person", "church", "in", [self.branch_a, ""]], filters_from_url(page["url"]))

	def test_birthdays_and_anniversaries_of_the_callers_churches(self):
		mine, theirs = self.make_pair("Born", life_events=[{"event_type": "Birth", "date": "1990-03-04"}])
		spouse = make_person("Spouse", LAST_NAME, church=self.branch_a).name
		married = {"marital_status": "Married", "anniversary": "2001-03-06"}
		husband = make_person("Husband", LAST_NAME, church=self.branch_a, spouse=spouse, **married).name

		rows = as_user(self.manager, ai.birthdays_and_anniversaries, **WINDOW)["rows"]

		people = {row["person"]: row for row in rows}
		self.assertEqual(people[mine]["turning"], 41)
		self.assertNotIn(theirs, people)
		couple = [row for row in rows if row["kind"] == "Anniversary" and spouse in (row["person"], husband)]
		self.assertEqual([row["years"] for row in couple], [30])

	def test_a_window_longer_than_the_cap_is_refused(self):
		self.assertRaises(
			frappe.ValidationError,
			as_user,
			self.manager,
			ai.birthdays_and_anniversaries,
			"2031-01-01",
			"2031-12-31",
		)

	def test_groups_without_a_leader_or_a_meeting_in_the_callers_churches(self):
		leader = ensure(
			"Group Role", {"role": "_Test AI Leader"}, {"role": "_Test AI Leader", "is_leader": 1}
		)
		person = make_person("Leader", LAST_NAME, church=self.branch_a).name
		quiet = self.make_group("_Test AI Quiet", self.branch_a)
		elsewhere = self.make_group("_Test AI Elsewhere", self.branch_b)
		busy = self.make_group("_Test AI Busy", self.branch_a, [{"person": person, "group_role": leader}])
		make_function("_Test AI Meeting", group=busy, church=self.branch_a, start_date=add_days(today(), -7))

		rows = {row["name"]: row for row in as_user(self.manager, ai.groups_needing_attention, 6)["rows"]}

		self.assertEqual(len(rows[quiet]["reasons"]), 2)
		self.assertNotIn(busy, rows)
		self.assertNotIn(elsewhere, rows)

	def make_group(self, group_name, church, members=()):
		group = {"doctype": "Group", "group_name": group_name, "church": church, "members": list(members)}
		return frappe.get_doc(group).insert(ignore_permissions=True).name

	def test_a_field_the_caller_may_not_read_is_left_out_not_sent_empty(self):
		member = {"membership": self.member_type, "membership_status": self.active}
		guest = make_person("Hidden", LAST_NAME, church=self.branch_a, **member).name
		attended = {"first_attended_on": today(), "last_attended_on": add_days(today(), -70)}
		frappe.db.set_value("Person", guest, attended)
		raise_permission_level(self, "Person", "full_name")

		for function, kwargs in (
			(ai.first_time_guests_without_follow_up, {"days": 7}),
			(ai.people_not_seen, {"weeks": 8}),
		):
			with self.subTest(function.__name__):
				rows = as_user(self.staff, function, **kwargs)["rows"]
				row = next(row for row in rows if row["name"] == guest)
				self.assertNotIn("full_name", row)

	def test_a_birthday_without_a_readable_birth_date_has_no_age(self):
		born = make_person(
			"Ageless",
			LAST_NAME,
			church=self.branch_a,
			life_events=[{"event_type": "Birth", "date": "1990-03-04"}],
		).name
		raise_permission_level(self, "Person", "birth_date")

		rows = as_user(self.staff, ai.birthdays_and_anniversaries, **WINDOW)["rows"]

		row = next(row for row in rows if row["person"] == born)
		self.assertNotIn("turning", row)

	def test_each_list_sends_one_page_and_the_total(self):
		member = {"membership": self.member_type, "membership_status": self.active}
		born = {"life_events": [{"event_type": "Birth", "date": "1990-03-04"}]}
		attended = {"first_attended_on": today(), "last_attended_on": add_days(today(), -70)}
		for person in self.make_pair("Paged", **member, **born) + self.make_pair(
			"Paged Too", **member, **born
		):
			frappe.db.set_value("Person", person, attended)
		for group_name in ("_Test AI Paged", "_Test AI Paged Too"):
			self.make_group(group_name, self.branch_a)

		for function, kwargs in (
			(ai.first_time_guests_without_follow_up, {"days": 7}),
			(ai.people_not_seen, {"weeks": 8}),
			(ai.birthdays_and_anniversaries, WINDOW),
			(ai.groups_needing_attention, {"weeks": 6}),
		):
			with self.subTest(function.__name__), patch.object(ai, "PAGE", 1):
				page = as_user(self.manager, function, **kwargs)
				self.assertEqual(len(page["rows"]), 1)
				self.assertGreaterEqual(page["total"], 2)


class TestBriefings(AITestCase):
	def test_staff_get_no_giving_or_care_keys_and_a_manager_gets_them_for_their_church(self):
		mine, theirs = self.make_pair("Giver")
		for person in (mine, theirs):
			frappe.db.set_value("Person", person, {"is_lapsed_giver": 1, "open_care_requests": 2})

		staff = as_user(self.staff, ai.get_person_briefing, mine)["summary"]
		manager = as_user(self.manager, ai.get_person_briefing, mine)["summary"]
		elsewhere = as_user(self.manager, ai.get_person_briefing, theirs)["summary"]

		self.assertEqual(staff["full_name"], f"Giver A {LAST_NAME}")
		self.assertFalse({"is_lapsed_giver", "open_care_requests"} & set(staff))
		self.assertEqual((manager["is_lapsed_giver"], manager["open_care_requests"]), (1, 2))
		self.assertFalse({"is_lapsed_giver", "open_care_requests"} & set(elsewhere))

	def test_records_follow_the_note_categories_and_carry_links(self):
		person = make_person("Noted", LAST_NAME, church=self.branch_a).name
		make_category("_Test AI Open Notes", view_roles=["Church Manager"])
		make_category("_Test AI Private Notes", is_private=1)
		shared = make_note(person, "_Test AI Open Notes", "<p>Asked about <b>baptism</b></p>")
		make_note(person, "_Test AI Private Notes", "Kept to myself")

		records = as_user(self.manager, ai.get_person_briefing, person)["records"]

		self.assertEqual(records["total"], 1)
		self.assertIn("Asked about baptism", records["rows"][0]["text"])
		self.assertTrue(records["rows"][0]["url"].endswith(shared))

	def test_a_child_is_briefed_like_anyone_else(self):
		child = make_person("Child", LAST_NAME, church=self.branch_a).name
		frappe.db.set_value("Person", child, "life_stage", "Child")

		summary = as_user(self.staff, ai.get_person_briefing, child)["summary"]

		self.assertEqual(summary["life_stage"], "Child")

	def test_a_masked_family_is_left_out_and_its_household_not_read(self):
		family = {"doctype": "Family", "family_name": "_Test AI Masked", "church": self.branch_a}
		family = frappe.get_doc(family).insert(ignore_permissions=True).name
		person = make_person("Masked", LAST_NAME, church=self.branch_a, family=family).name
		make_property_setter("Person", "family", "mask", 1, "Check")
		frappe.clear_cache(doctype="Person")
		self.addCleanup(frappe.clear_cache)

		briefing = as_user(self.staff, ai.get_person_briefing, person)

		self.assertNotIn("family", briefing["summary"])
		self.assertEqual(briefing["household"], [])

	def test_each_briefing_writes_one_access_log_row(self):
		person = make_person("Logged", LAST_NAME, church=self.branch_a).name
		group = frappe.get_doc({"doctype": "Group", "group_name": "_Test AI Logged", "church": self.branch_a})
		group = group.insert(ignore_permissions=True).name
		for function, name, method in (
			(ai.get_person_briefing, person, ai.PERSON_BRIEFING),
			(ai.get_group_briefing, group, ai.GROUP_BRIEFING),
		):
			filters = {"user": self.staff, "method": method, "reference_document": name}
			pop_logs("Access Log", filters)
			as_user(self.staff, function, name)
			with self.subTest(method):
				self.assertEqual(len(pop_logs("Access Log", filters)), 1)

	def test_a_group_briefing_has_members_leaders_meetings_and_requests(self):
		leader_role = ensure(
			"Group Role", {"role": "_Test AI Leader"}, {"role": "_Test AI Leader", "is_leader": 1}
		)
		leader = make_person("Leads", LAST_NAME, church=self.branch_a).name
		member = make_person("Belongs", LAST_NAME, church=self.branch_a).name
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": "_Test AI Briefed",
				"church": self.branch_a,
				"members": [{"person": leader, "group_role": leader_role}, {"person": member}],
			}
		).insert(ignore_permissions=True)
		meeting = make_function(
			"_Test AI Gathering", group=group.name, church=self.branch_a, start_date=add_days(today(), -3)
		)
		joiner = make_person("Joins", LAST_NAME, church=self.branch_a).name
		frappe.get_doc({"doctype": "Group Join Request", "person": joiner, "group": group.name}).insert(
			ignore_permissions=True
		)

		with patch.object(ai, "PAGE", 1):
			briefing = as_user(self.staff, ai.get_group_briefing, group.name)

		self.assertEqual(briefing["member_count"], 2)
		self.assertEqual(len(briefing["members"]), 1)
		self.assertEqual([row["person"] for row in briefing["leaders"]], [leader])
		self.assertEqual([row["name"] for row in briefing["meetings"]], [meeting.name])
		self.assertEqual([row["person"] for row in briefing["open_join_requests"]], [joiner])

	def test_another_churchs_group_is_refused(self):
		group = frappe.get_doc({"doctype": "Group", "group_name": "_Test AI Theirs", "church": self.branch_b})
		group = group.insert(ignore_permissions=True).name

		self.assertRaises(frappe.PermissionError, as_user, self.staff, ai.get_group_briefing, group)
