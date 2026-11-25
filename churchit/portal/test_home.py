# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from churchit.church_people.test_household import link_user, make_household
from churchit.portal import home
from churchit.portal.test_events import make_sign_up
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)


class TestMemberAppHome(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.family, cls.father, *_rest = make_household("_Test Home Family")
		cls.member = link_user(cls.father, "portal-home-member@example.com")
		cls.addClassCleanup(frappe.clear_cache)

	def setUp(self):
		super().setUp()
		frappe.local.form_dict = frappe._dict()

	def test_a_login_with_no_person_is_refused(self):
		frappe.set_user(ensure_user("portal-home-nobody@example.com", "Nobody"))
		with self.assertRaises(frappe.PermissionError):
			home.get_home()

	def test_a_group_meeting_of_the_members_group_is_in_the_week(self):
		group = make_group("_Test Home Group", self.father)
		make_function(
			"_Test Home Meeting", group=group, start_date=add_days(today(), 2), start_time="19:00:00"
		)

		frappe.set_user(self.member)
		days = home.get_home()["week"]

		entry = next(entry for day in days for entry in day["entries"] if entry["kind"] == "group")
		self.assertEqual(entry["title"], "_Test Home Group")
		self.assertEqual(entry["time"], "19:00:00")
		self.assertEqual(entry["route"], f"/groups/{group}")

	def test_a_group_the_member_is_not_in_is_not_shown(self):
		stranger = make_person("_Test Home", "Stranger").name
		group = make_group("_Test Home Other Group", stranger)
		make_function("_Test Home Other Meeting", group=group, start_date=add_days(today(), 1))

		frappe.set_user(self.member)
		kinds = [entry["kind"] for day in home.get_home()["week"] for entry in day["entries"]]

		self.assertNotIn("group", kinds)

	def test_a_group_kept_off_the_portal_is_not_announced(self):
		group = make_group("_Test Home Hidden Group", self.father, show_in_portal=0)
		make_function("_Test Home Hidden Meeting", group=group, start_date=add_days(today(), 1))

		frappe.set_user(self.member)
		kinds = [entry["kind"] for day in home.get_home()["week"] for entry in day["entries"]]

		self.assertNotIn("group", kinds)

	def test_a_meeting_after_the_week_goes_to_looking_ahead(self):
		group = make_group("_Test Home Later Group", self.father)
		make_function("_Test Home Later Meeting", group=group, start_date=add_days(today(), 20))

		frappe.set_user(self.member)
		result = home.get_home()

		self.assertEqual([entry["title"] for entry in result["ahead"]], ["_Test Home Later Group"])
		self.assertFalse(result["week"])

	def test_members_only_pages_list_only_for_a_member_who_may_open_them(self):
		page = frappe.get_doc(
			{
				"doctype": "Web Page",
				"title": "_Test Home Corner",
				"route": "test-home-corner",
				"published": 1,
				"members_only": 1,
				"content_type": "Rich Text",
				"main_section": "x",
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self.member)
		self.assertIn(page.name, [row["name"] for row in home.get_home()["members_only_pages"]])

		frappe.set_user("Administrator")
		visitor = make_person("_Test Home", "Visitor", membership="Visitor")
		frappe.set_user(link_user(visitor.name, "portal-home-visitor@example.com"))
		self.assertEqual(home.get_home()["members_only_pages"], [])

	def test_a_sign_up_for_a_function_today_is_in_the_week(self):
		function = make_function(
			"_Test Home Tonight", allow_sign_ups=1, start_date=today(), start_time="19:00:00"
		)
		make_sign_up(function.name, self.father, owner=self.member)

		frappe.set_user(self.member)
		days = home.get_home()["week"]

		self.assertEqual(
			[(day["is_today"], entry["title"]) for day in days for entry in day["entries"]],
			[(True, "_Test Home Tonight")],
		)

	def test_a_section_of_a_switched_off_page_is_empty(self):
		frappe.set_user(self.member)
		sections = {
			"community-prayer-requests": ("get_prayer_requests", "prayer_requests", [{"name": "x"}], []),
			"announcements": ("get_notices", "notices", [{"name": "x"}], []),
			"bulletins": ("get_newest_bulletin", "bulletin", {"name": "x"}, None),
			"ministry-team": ("get_requests_to_answer", "needs_answer", [{"name": "x"}], []),
		}
		for page, (getter, key, value, empty) in sections.items():
			with self.subTest(page=page), patch.object(home, getter, return_value=value):
				self.assertEqual(home.get_home()[key], value)
				with patch.object(home, "get_hidden_pages", return_value={page}):
					self.assertEqual(home.get_home()[key], empty)

	def test_an_entry_of_a_switched_off_page_has_no_link_and_serving_is_left_out(self):
		group = make_group("_Test Home Linked Group", self.father)
		make_function("_Test Home Linked Meeting", group=group, start_date=add_days(today(), 1))
		frappe.set_user(self.member)

		with patch.object(home, "get_hidden_pages", return_value={"groups"}):
			entry = home.get_home()["week"][0]["entries"][0]
		self.assertIsNone(entry["route"])

		with patch.object(home, "get_hidden_pages", return_value={"ministry-team"}):
			with patch.object(home, "get_serving_entries") as serving:
				home.get_home()
		serving.assert_not_called()

	def test_a_notice_that_is_a_json_string_is_still_sanitized(self):
		bulletin = frappe._dict(
			name="B",
			function_name="Sunday",
			function_date=today(),
			announcements='"<img src=x onerror=alert(1)>"',
		)
		with patch.object(home.frappe, "get_all", return_value=[bulletin]):
			notice = home.get_notices()[0]

		self.assertNotIn("onerror", notice["announcements"])

	def test_notices_the_bulletin_and_prayer_requests_come_from_the_members_own_church(self):
		"""A shared bulletin reaches every church, and a ?church= on the request does not pick the church."""
		member = ensure_user("portal-home-branch@example.com", "Branch")
		make_person("_Test Home", "Branch", church=self.branch_a, user=member)
		# Each bulletin left out is newer than the ones shown, so a leak would push one off the list.
		make_bulletin("2040-01-29", church=self.branch_b)
		make_bulletin("2040-01-22", church=self.branch_a, publish=0)
		mine = make_bulletin("2040-01-15", church=self.branch_a)
		make_bulletin("2040-01-08", church=self.branch_a, share_announcements=0)
		joint = make_bulletin("2040-01-01", is_shared=1)
		request = make_prayer_request("_Test Home Ours", self.branch_a)
		make_prayer_request("_Test Home Theirs", self.branch_b)
		make_prayer_request("_Test Home Private", self.branch_a, visibility="Private")
		frappe.db.set_value("Church", self.branch_b, "publish", 1)

		frappe.set_user(member)
		frappe.local.form_dict = frappe._dict(church=self.branch_b)
		result = home.get_home()

		self.assertEqual([notice["name"] for notice in result["notices"]], [mine, joint])
		self.assertEqual(result["bulletin"]["name"], mine)
		self.assertEqual([row["name"] for row in result["prayer_requests"]], [request])


def make_bulletin(date, publish=1, share_announcements=1, **function_values):
	"""The name of a bulletin with announcements, for a new function on *date*."""
	function = make_function(f"_Test Home Service {date}", start_date=date, **function_values)
	bulletin = frappe.get_doc(
		{
			"doctype": "Bulletin",
			"function": function.name,
			"publish": publish,
			"share_announcements": share_announcements,
			"announcements": "<p>_Test Home notice</p>",
		}
	)
	return bulletin.insert(ignore_permissions=True).name


def make_prayer_request(title, church, visibility="Whole Church"):
	"""The name of an open prayer request of *church*, approved for the prayer list."""
	request = frappe.get_doc(
		{
			"doctype": "Prayer Request",
			"title": title,
			"type": ensure("Prayer Request Type", {"type": "_Test Home"}),
			"church": church,
			"visibility": visibility,
			"approved_for_list": 1,
		}
	)
	return request.insert(ignore_permissions=True).name


def make_group(title, member, show_in_portal=1):
	group = frappe.get_doc(
		{
			"doctype": "Group",
			"group_name": title,
			"show_in_portal": show_in_portal,
			"members": [{"person": member}],
		}
	).insert(ignore_permissions=True)
	return group.name
