# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The groups endpoints of the member app, and the live hints their changes send."""

from unittest import mock

import frappe
from frappe.utils import add_days, today

from churchit.church_people.group_api import decide_join_request, join_group, leave_group
from churchit.church_people.group_meetings import record_group_attendance
from churchit.portal.groups import add_group_file, get_group, get_group_files, get_leader_view, get_my_groups
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure,
	ensure_user,
	make_function,
	make_person,
	make_two_churches,
)

PUBLISH = "churchit.portal.realtime.frappe.publish_realtime"


def hints(publish):
	"""[(user, topic)] of the portal hints *publish* received."""
	return [
		(call.kwargs["user"], call.args[1]["topic"])
		for call in publish.call_args_list
		if call.args[0] == "churchit_portal"
	]


LEADER_ROLE = "_Test Portal Group Leader"
MEMBER_ROLE = "_Test Portal Group Member"


class TestPortalGroups(RollbackEachTest):
	"""Two churches. In church A: a leader, a co-leader, a member and an outsider, and three groups."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		ensure("Group Role", {"role": LEADER_ROLE}, {"role": LEADER_ROLE, "is_leader": 1})
		ensure("Group Role", {"role": MEMBER_ROLE}, {"role": MEMBER_ROLE, "is_leader": 0})
		ensure("Group Role", {"role": "Member"})
		cls.leader, cls.leader_user = cls.make_member("Leader")
		cls.co_leader, cls.co_leader_user = cls.make_member("Coleader")
		cls.member, cls.member_user = cls.make_member("Member")
		cls.outsider, cls.outsider_user = cls.make_member("Outsider")
		cls.foreign_leader, _foreign_user = cls.make_member("Foreigner", church=cls.other_church)

	@classmethod
	def make_member(cls, first_name, church=None):
		email = f"_test_portal_group_{first_name.lower()}@example.com"
		user = ensure_user(email, f"_Test Portal {first_name}")
		person = make_person(
			first_name,
			"_Test Portal Group",
			church=church or cls.church,
			user=user,
			share_email=1,
			emails=[{"email_address": email}],
		)
		return person.name, user

	def setUp(self):
		super().setUp()
		self.group = self.make_group("_Test Portal Open", show_in_portal=1, public=1)
		self.hidden_group = self.make_group("_Test Portal Hidden", show_in_portal=0, public=0)
		self.foreign_group = self.make_group(
			"_Test Portal Foreign",
			church=self.other_church,
			members=[(self.foreign_leader, LEADER_ROLE)],
			public=1,
		)

	def make_group(self, name, church=None, members=None, **values):
		group = frappe.get_doc(
			{
				"doctype": "Group",
				"group_name": name,
				"church": church or self.church,
				"show_in_portal": 1,
				**values,
			}
		)
		for person, role in members or (
			[(self.leader, LEADER_ROLE), (self.co_leader, LEADER_ROLE), (self.member, MEMBER_ROLE)]
		):
			group.append("members", {"person": person, "group_role": role})
		return group.insert(ignore_permissions=True).name

	def make_file(self, group, title="_Test Portal Roster"):
		frappe.set_user("Administrator")
		file = frappe.get_doc(
			{"doctype": "File", "file_name": f"{title}.txt", "content": b"hello", "is_private": 1}
		).insert()
		return frappe.get_doc(
			{"doctype": "Group File", "group": group, "title": title, "attached_file": file.file_url}
		).insert(ignore_permissions=True)

	def upload(self, user, file_name="_test_portal_upload.txt"):
		"""A private file *user* uploaded with no document yet, as the app's file picker leaves it."""
		frappe.set_user(user)
		return frappe.get_doc(
			{"doctype": "File", "file_name": file_name, "content": file_name.encode(), "is_private": 1}
		).insert()

	def make_meeting(self, group, days, **values):
		return make_function(
			f"_Test Portal Meeting {days}",
			church=self.church,
			group=group,
			start_date=add_days(today(), days),
			start_time="19:00:00",
			**values,
		)

	def test_my_groups_lists_the_members_groups_and_who_leads_them(self):
		frappe.set_user(self.member_user)

		result = get_my_groups()

		by_name = {row["name"]: row for row in result["groups"]}
		self.assertIn(self.group, by_name)
		self.assertEqual(by_name[self.group]["group_name"], "_Test Portal Open")
		self.assertIn("Leader", by_name[self.group]["leaders"])
		self.assertIn("Coleader", by_name[self.group]["leaders"])
		self.assertFalse(by_name[self.group]["is_leader"])
		self.assertTrue(by_name[self.group]["can_leave"])

	def test_a_group_not_shown_in_the_portal_is_listed_for_its_leader_only(self):
		frappe.set_user(self.member_user)
		self.assertNotIn(self.hidden_group, [row["name"] for row in get_my_groups()["groups"]])

		frappe.set_user(self.leader_user)
		self.assertIn(self.hidden_group, [row["name"] for row in get_my_groups()["groups"]])

	def test_the_only_leader_cannot_leave(self):
		sole = self.make_group("_Test Portal Sole", members=[(self.leader, LEADER_ROLE)])
		frappe.set_user(self.leader_user)

		by_name = {row["name"]: row for row in get_my_groups()["groups"]}

		self.assertFalse(by_name[sole]["can_leave"])
		self.assertTrue(by_name[self.group]["can_leave"])

	def test_the_picker_offers_open_groups_of_this_church_and_marks_a_request(self):
		approval = self.make_group("_Test Portal Approval", requires_approval=1, public=1)
		frappe.set_user(self.outsider_user)

		joinable = {row["name"] for row in get_my_groups()["joinable"]}

		self.assertEqual(joinable, {self.group, approval})
		self.assertNotIn(self.foreign_group, joinable)

		join_group(approval, "May I?")
		result = get_my_groups()
		self.assertEqual([row["name"] for row in result["waiting"]], [approval])
		self.assertNotIn(approval, [row["name"] for row in result["joinable"]])

	def test_my_groups_refuses_a_guest_and_a_login_without_a_person(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			get_my_groups()

		frappe.set_user(ensure_user("_test_portal_group_nobody@example.com", "_Test Nobody"))
		with self.assertRaises(frappe.PermissionError):
			get_my_groups()

	def test_a_switched_off_page_is_refused(self):
		frappe.set_user(self.member_user)
		with mock.patch("churchit.church_website.pages.get_switched_off_pages", return_value={"groups"}):
			with self.assertRaises(frappe.PermissionError):
				get_my_groups()
			with self.assertRaises(frappe.PermissionError):
				get_group(self.group)

		with mock.patch("churchit.church_website.pages.get_switched_off_pages", return_value={"group-files"}):
			with self.assertRaises(frappe.PermissionError):
				get_group_files()

			self.make_file(self.group)
			frappe.set_user(self.member_user)
			result = get_group(self.group)
			self.assertEqual(result["files"], [])
			self.assertFalse(result["show_files"])

	def test_one_group_shows_its_meetings_and_files_to_a_member(self):
		self.make_meeting(self.group, 3)
		self.make_meeting(self.group, 10)
		self.make_meeting(self.group, -3)
		self.make_file(self.group)
		frappe.set_user(self.member_user)

		result = get_group(self.group)

		self.assertEqual(result["group_name"], "_Test Portal Open")
		self.assertEqual(result["next_meeting"]["date"], add_days(today(), 3))
		self.assertEqual(result["next_meeting"]["time"], "19:00:00")
		self.assertEqual([row["date"] for row in result["later_meetings"]], [add_days(today(), 10)])
		self.assertEqual([row["title"] for row in result["files"]], ["_Test Portal Roster"])

	def test_a_stored_link_that_is_not_a_private_file_is_not_returned(self):
		self.make_file(self.group)
		frappe.db.set_value("Group File", {"group": self.group}, "attached_file", "javascript:alert(1)")
		frappe.set_user(self.member_user)

		self.assertEqual(get_group(self.group)["files"], [])
		self.assertEqual(get_group_files()["items"], [])

	def test_one_group_is_refused_to_a_non_member_and_for_another_church(self):
		frappe.set_user(self.outsider_user)
		with self.assertRaises(frappe.PermissionError):
			get_group(self.group)

		frappe.set_user(self.member_user)
		with self.assertRaises(frappe.PermissionError):
			get_group(self.foreign_group)

	def test_a_member_cannot_open_a_group_not_shown_in_the_portal_but_its_leader_can(self):
		frappe.set_user(self.member_user)
		with self.assertRaises(frappe.PermissionError):
			get_group(self.hidden_group)

		frappe.set_user(self.leader_user)
		self.assertTrue(get_group(self.hidden_group)["is_leader"])

	def test_files_come_only_from_the_members_groups_and_a_leader_may_add(self):
		own = self.make_file(self.group, "_Test Portal Own")
		other = self.make_group("_Test Portal Other", members=[(self.co_leader, LEADER_ROLE)])
		self.make_file(other, "_Test Portal Elsewhere")

		frappe.set_user(self.member_user)
		result = get_group_files()
		self.assertEqual([row["name"] for row in result["items"]], [own.name])
		self.assertFalse(result["can_add"])
		self.assertEqual(result["groups"], [])

		frappe.set_user(self.leader_user)
		result = get_group_files()
		self.assertTrue(result["can_add"])
		self.assertIn(self.group, [row["value"] for row in result["groups"]])
		self.assertNotIn(other, [row["value"] for row in result["groups"]])

	def test_the_leader_view_shows_the_roster_with_shared_contacts(self):
		frappe.set_user(self.leader_user)

		group = get_leader_view()["groups"][0]
		roster = {row["name"]: row for row in group["roster"]}

		self.assertEqual(roster[self.member]["email"], "_test_portal_group_member@example.com")
		self.assertEqual(roster[self.member]["group_role"], MEMBER_ROLE)
		self.assertEqual(group["upcoming"]["has_schedule"], False)

		frappe.db.set_value("Person", self.member, "share_email", 0)
		roster = {row["name"]: row for row in get_leader_view(self.group)["groups"][0]["roster"]}
		self.assertIsNone(roster[self.member]["email"])

	def test_the_leader_view_offers_only_the_ways_the_site_can_send(self):
		frappe.set_user(self.leader_user)
		for can_email, can_text in ((False, False), (True, False), (False, True)):
			with (
				mock.patch("churchit.portal.groups.can_send_email", return_value=can_email),
				mock.patch("churchit.portal.groups.can_send_texts", return_value=can_text),
			):
				result = get_leader_view(self.group)
			self.assertEqual((result["can_send_email"], result["can_send_texts"]), (can_email, can_text))

	def test_a_group_with_no_recent_meeting_gives_its_next_date_or_its_schedule(self):
		frappe.set_user(self.leader_user)
		self.assertEqual(
			get_leader_view(self.group)["groups"][0]["upcoming"],
			{"next_date": None, "next_date_label": None, "has_schedule": False},
		)

		frappe.set_user("Administrator")
		ahead = self.make_meeting(self.group, 10)
		self.make_meeting(
			self.group, 100, auto_repeat=1, repeat_frequency="Weekly", repeat_day_of_week="Tuesday"
		)
		frappe.set_user(self.leader_user)
		upcoming = get_leader_view(self.group)["groups"][0]["upcoming"]

		self.assertEqual(upcoming["next_date"], str(ahead.start_date))
		self.assertTrue(upcoming["next_date_label"])
		self.assertTrue(upcoming["has_schedule"])

	def test_the_leader_view_narrows_to_one_group_and_ignores_a_group_not_led(self):
		frappe.set_user(self.leader_user)
		self.assertEqual(len(get_leader_view()["groups"]), 2)
		self.assertEqual([row["name"] for row in get_leader_view(self.group)["groups"]], [self.group])
		self.assertEqual(len(get_leader_view(self.foreign_group)["groups"]), 2)

	def test_the_leader_view_is_refused_to_a_member_who_leads_nothing(self):
		frappe.set_user(self.member_user)
		with self.assertRaises(frappe.PermissionError):
			get_leader_view()

	def test_the_leader_view_lists_meetings_with_attendance_and_open_requests(self):
		meeting = self.make_meeting(self.group, -2)
		approval = self.make_group("_Test Portal Approval", requires_approval=1, public=1)
		frappe.set_user(self.outsider_user)
		request = join_group(approval, "Please")["request"]

		frappe.set_user(self.leader_user)
		record_group_attendance(meeting.name, f'["{self.member}"]', "[]", 0)
		result = {row["name"]: row for row in get_leader_view()["groups"]}

		self.assertEqual(result[self.group]["meetings"][0]["attendance"], {self.member: "Confirmed"})
		self.assertEqual(result[approval]["join_requests"][0]["name"], request)
		self.assertEqual(result[approval]["join_requests"][0]["message"], "Please")
		self.assertIsNone(result[self.group]["upcoming"])

	def test_a_join_request_tells_the_leaders_and_the_member(self):
		approval = self.make_group("_Test Portal Approval", requires_approval=1, public=1)
		frappe.set_user(self.outsider_user)

		with mock.patch(PUBLISH) as publish:
			join_group(approval, "Please")

		sent = set(hints(publish))
		self.assertEqual(
			sent,
			{
				(self.leader_user, "group-requests"),
				(self.co_leader_user, "group-requests"),
				(self.outsider_user, "groups"),
			},
		)

	def test_a_decision_tells_the_member_and_the_other_leader(self):
		approval = self.make_group("_Test Portal Approval", requires_approval=1, public=1)
		frappe.set_user(self.outsider_user)
		request = join_group(approval, "Please")["request"]
		frappe.set_user(self.leader_user)

		with mock.patch(PUBLISH) as publish:
			decide_join_request(request, "1")

		sent = set(hints(publish))
		self.assertIn((self.outsider_user, "groups"), sent)
		self.assertIn((self.co_leader_user, "group-requests"), sent)
		self.assertNotIn((self.leader_user, "group-requests"), sent)

	def test_leaving_and_joining_send_a_groups_hint_to_the_member(self):
		frappe.set_user(self.member_user)
		with mock.patch(PUBLISH) as publish:
			leave_group(self.group)
		self.assertEqual(hints(publish), [(self.member_user, "groups")])

		with mock.patch(PUBLISH) as publish:
			join_group(self.group)
		self.assertEqual(hints(publish), [(self.member_user, "groups")])

	def test_attendance_tells_the_other_leaders_only(self):
		meeting = self.make_meeting(self.group, -1)
		frappe.set_user(self.leader_user)

		with mock.patch(PUBLISH) as publish:
			record_group_attendance(meeting.name, f'["{self.member}"]', "[]", 0)

		self.assertEqual(hints(publish), [(self.co_leader_user, "group-meetings")])

	def test_a_new_file_tells_each_member_of_the_group(self):
		with mock.patch(PUBLISH) as publish:
			self.make_file(self.group)

		self.assertEqual(
			set(hints(publish)),
			{(user, "group-files") for user in (self.leader_user, self.co_leader_user, self.member_user)},
		)

	def test_a_leader_shares_a_file_that_the_members_of_the_group_can_open(self):
		file = self.upload(self.leader_user)

		with mock.patch(PUBLISH) as publish:
			name = add_group_file(self.group, "_Test Portal Notes", file.file_url)["name"]

		self.assertIn((self.member_user, "group-files"), hints(publish))
		frappe.set_user("Administrator")
		attached = frappe.get_doc("File", file.name)
		self.assertEqual((attached.attached_to_doctype, attached.attached_to_name), ("Group File", name))
		self.assertTrue(attached.is_private)
		frappe.set_user(self.member_user)
		self.assertTrue(attached.is_downloadable())

	def test_only_a_leader_of_the_group_shares_a_file_with_it(self):
		for user, group in ((self.member_user, self.group), (self.leader_user, self.foreign_group)):
			file = self.upload(user)
			with self.assertRaises(frappe.PermissionError):
				add_group_file(group, "_Test Portal Refused", file.file_url)

		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Group File", {"title": "_Test Portal Refused"}))

	def test_a_leader_cannot_share_a_file_they_cannot_open_or_a_public_one(self):
		staff_file = self.upload("Administrator", "_test_portal_staff_only.txt")
		frappe.set_user(self.leader_user)

		with self.assertRaises(frappe.PermissionError):
			add_group_file(self.group, "_Test Portal Taken", staff_file.file_url)
		with self.assertRaisesRegex(frappe.ValidationError, "private"):
			add_group_file(self.group, "_Test Portal Public", "/files/_test_portal_public.txt")

		frappe.set_user("Administrator")
		self.assertIsNone(frappe.db.get_value("File", staff_file.name, "attached_to_name"))

	def test_no_file_is_shared_while_group_files_is_switched_off(self):
		file = self.upload(self.leader_user)

		with mock.patch("churchit.church_website.pages.get_switched_off_pages", return_value={"group-files"}):
			with self.assertRaises(frappe.PermissionError):
				add_group_file(self.group, "_Test Portal Off", file.file_url)
