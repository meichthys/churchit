# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe

from churchit.church_prayers.api import create_prayer
from churchit.portal import care
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person, make_two_churches

PUBLISH = "churchit.portal.realtime.frappe.publish_realtime"
PRIVATE_FIELDS = {"requestor", "owner", "modified_by", "church", "approved_for_list", "end_date"}


def add_member(email, church, *roles):
	user = ensure_user(email, "Member", roles=roles or ("Church User",))
	make_person("_Test Care", email.split("@")[0], church=church, user=user)
	return user


def make_prayer_request(user, title, **values):
	frappe.set_user(user)
	try:
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": title,
				"type": ensure("Prayer Request Type", {"type": "Health"}),
				"visibility": "Whole Church",
				**values,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.set_user("Administrator")


class CareCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church, cls.other_church = make_two_churches()
		cls.member = add_member("_test_portal_care_a@example.com", cls.church)
		cls.neighbour = add_member("_test_portal_care_b@example.com", cls.church)
		cls.stranger = add_member("_test_portal_care_c@example.com", cls.other_church)
		cls.team = add_member(
			"_test_portal_care_team@example.com", cls.church, "Church User", "Church Prayer Team"
		)

	def names(self, result):
		return [row["name"] for row in result["items"]]

	def portal_calls(self, publish):
		return [call for call in publish.call_args_list if call.args[0] == "churchit_portal"]

	def switch_off(self, route):
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": route})[0].enabled = 0
		features.save()


class TestPrayerLists(CareCase):
	def test_my_requests_are_the_members_own_only(self):
		mine = make_prayer_request(self.member, "_Test Mine", visibility="Private")
		theirs = make_prayer_request(self.neighbour, "_Test Theirs")

		frappe.set_user(self.member)
		names = self.names(care.get_my_prayer_requests())

		self.assertIn(mine.name, names)
		self.assertNotIn(theirs.name, names)

	def test_the_form_names_the_members_person_and_the_types(self):
		frappe.set_user(self.member)
		form = care.get_prayer_form()

		self.assertTrue(form["me"]["name"])
		self.assertIn("Health", [row["name"] for row in form["types"]])
		self.assertEqual(
			[row["name"] for row in form["visibilities"]], ["Private", "Prayer Team", "Whole Church"]
		)

	def test_the_prayer_list_shows_open_requests_of_the_members_church(self):
		shown = make_prayer_request(self.neighbour, "_Test Shown")
		private = make_prayer_request(self.neighbour, "_Test Private", visibility="Private")
		elsewhere = make_prayer_request(self.stranger, "_Test Elsewhere")
		unapproved = make_prayer_request(self.neighbour, "_Test Unapproved")
		frappe.db.set_value("Prayer Request", unapproved.name, "approved_for_list", 0)
		ended = make_prayer_request(self.neighbour, "_Test Ended", end_date="2000-01-01 00:00:00")

		frappe.set_user(self.member)
		names = self.names(care.get_community_requests())

		self.assertIn(shown.name, names)
		for hidden in (private, elsewhere, unapproved, ended):
			self.assertNotIn(hidden.name, names)

	def test_the_prayer_list_sends_no_requester_or_owner(self):
		make_prayer_request(self.neighbour, "_Test Shown")
		frappe.set_user(self.member)
		row = care.get_community_requests()["items"][0]

		self.assertFalse(PRIVATE_FIELDS & set(row))

	def test_only_the_prayer_team_reads_prayer_team_requests(self):
		team_only = make_prayer_request(self.neighbour, "_Test Team Only", visibility="Prayer Team")

		frappe.set_user(self.member)
		self.assertNotIn(team_only.name, self.names(care.get_community_requests()))
		with self.assertRaises(frappe.PermissionError):
			care.get_community_request(team_only.name)

		frappe.set_user(self.team)
		self.assertIn(team_only.name, self.names(care.get_community_requests()))
		self.assertTrue(care.get_community_request(team_only.name)["is_team_only"])

	def test_a_request_of_another_church_or_a_private_one_is_refused(self):
		elsewhere = make_prayer_request(self.stranger, "_Test Elsewhere")
		private = make_prayer_request(self.neighbour, "_Test Private", visibility="Private")

		frappe.set_user(self.member)
		for request in (elsewhere, private):
			with self.assertRaises(frappe.PermissionError):
				care.get_community_request(request.name)

	def test_a_page_switched_off_is_refused(self):
		self.switch_off("community-prayer-requests")
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			care.get_community_requests()

	def test_a_guest_is_refused(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			care.get_my_prayer_requests()


class TestPraying(CareCase):
	def test_praying_is_seen_as_prayed_today_and_tells_the_owner(self):
		request = make_prayer_request(self.neighbour, "_Test Pray")

		frappe.set_user(self.member)
		with patch(PUBLISH) as publish:
			create_prayer(request.name, "Lord, help")

		publish.assert_any_call(
			"churchit_portal",
			{"topic": "prayer", "name": request.name},
			user=self.neighbour,
			after_commit=True,
		)
		row = care.get_community_request(request.name)
		self.assertTrue(row["prayed_today"])
		self.assertEqual(row["prayer_count"], 1)

	def test_a_comment_is_listed_and_tells_the_owner(self):
		request = make_prayer_request(self.neighbour, "_Test Comment")

		frappe.set_user(self.member)
		with patch(PUBLISH) as publish:
			result = care.add_prayer_comment(request.name, "Praying for you")

		publish.assert_any_call(
			"churchit_portal",
			{"topic": "prayer", "name": request.name},
			user=self.neighbour,
			after_commit=True,
		)
		comment = result["comments"][0]
		self.assertEqual(comment["content"], "Praying for you")
		self.assertNotIn("comment_email", comment)

	def test_a_comment_shows_plain_text_not_entities(self):
		request = make_prayer_request(self.neighbour, "_Test Entities")

		frappe.set_user(self.member)
		result = care.add_prayer_comment(request.name, "Praying for Tom & Ann <3")

		self.assertEqual(result["comments"][0]["content"], "Praying for Tom & Ann <3")

	def test_a_comment_with_a_link_is_refused(self):
		request = make_prayer_request(self.neighbour, "_Test Link")
		frappe.set_user(self.member)

		with self.assertRaises(frappe.ValidationError):
			care.add_prayer_comment(request.name, "see https://example.com")

	def test_a_comment_on_a_request_the_member_cannot_read_is_refused(self):
		private = make_prayer_request(self.neighbour, "_Test Private", visibility="Private")
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			care.add_prayer_comment(private.name, "Hello")


class TestRequestComments(CareCase):
	def test_the_owner_comments_and_reads_on_a_prayer_request(self):
		request = make_prayer_request(self.member, "_Test Own Comment", visibility="Private")

		frappe.set_user(self.member)
		with patch(PUBLISH) as publish:
			result = care.add_request_comment("prayer-request", request.name, "Thank you")

		publish.assert_any_call(
			"churchit_portal", {"topic": "prayer", "name": request.name}, user=self.member, after_commit=True
		)
		self.assertEqual([row["content"] for row in result["comments"]], ["Thank you"])
		self.assertEqual(care.get_request_comments("prayer-request", request.name), result)
		self.assertNotIn("comment_email", result["comments"][0])

	def test_the_owner_comments_on_an_alms_request(self):
		frappe.set_user(self.member)
		person = frappe.db.get_value("Person", {"user": self.member}, "name")
		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"recipient_type": "Person",
				"recipient": person,
				"description": "Rent",
				"amount": 50,
			}
		).insert(ignore_permissions=True)

		result = care.add_request_comment("alms-request", alms.name, "Any news?")

		self.assertEqual(result["comments"][0]["content"], "Any news?")

	def test_another_member_cannot_comment_or_read(self):
		request = make_prayer_request(self.member, "_Test Not Yours", visibility="Whole Church")

		frappe.set_user(self.neighbour)
		with self.assertRaises(frappe.PermissionError):
			care.add_request_comment("prayer-request", request.name, "Hello")
		with self.assertRaises(frappe.PermissionError):
			care.get_request_comments("prayer-request", request.name)

	def test_only_the_comment_forms_are_accepted(self):
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			care.get_request_comments("care-request", "x")

	def test_a_switched_off_page_is_refused(self):
		request = make_prayer_request(self.member, "_Test Off", visibility="Private")
		self.switch_off("prayer-request")

		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			care.add_request_comment("prayer-request", request.name, "Hello")
		with self.assertRaises(frappe.PermissionError):
			care.get_request_comments("prayer-request", request.name)


class TestCareAndAlms(CareCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.category = ensure("Care Request Type", {"type": "_Test Meals"})

	def make_care(self, user, **values):
		frappe.set_user(user)
		try:
			return frappe.get_doc(
				{
					"doctype": "Care Request",
					"category": self.category,
					"description": "Needs a hand",
					**values,
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	def make_alms(self, user, recipient):
		frappe.set_user(user)
		try:
			return frappe.get_doc(
				{
					"doctype": "Alms Request",
					"recipient_type": "Person",
					"recipient": recipient,
					"description": "Rent",
					"amount": 50,
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

	def test_my_care_requests_are_the_members_own_only(self):
		mine = self.make_care(self.member)
		theirs = self.make_care(self.neighbour)

		frappe.set_user(self.member)
		names = self.names(care.get_my_care_requests())

		self.assertIn(mine.name, names)
		self.assertNotIn(theirs.name, names)

	def test_a_staff_web_form_save_keeps_the_status_it_has(self):
		staff = add_member("_test_portal_care_staff@example.com", self.church, "Church Manager")
		person = frappe.db.get_value("Person", {"user": staff}, "name")

		def save_from_web_form(doc):
			frappe.set_user(staff)
			frappe.flags.in_web_form = True
			try:
				doc.status = ""
				doc.save(ignore_permissions=True)
			finally:
				frappe.flags.in_web_form = False
				frappe.set_user("Administrator")

		request = self.make_care(staff)
		frappe.db.set_value("Care Request", request.name, "status", "In Progress")
		save_from_web_form(frappe.get_doc("Care Request", request.name))
		self.assertEqual(frappe.db.get_value("Care Request", request.name, "status"), "In Progress")

		alms = frappe.get_doc(
			{
				"doctype": "Alms Request",
				"requestor": person,
				"recipient_type": "Person",
				"recipient": person,
				"description": "Rent",
				"amount": 5,
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Alms Request", alms.name, "status", "Approved")
		save_from_web_form(frappe.get_doc("Alms Request", alms.name))
		self.assertEqual(frappe.db.get_value("Alms Request", alms.name, "status"), "Approved")

		frappe.set_user(staff)
		frappe.flags.in_web_form = True
		try:
			new = frappe.get_doc(
				{
					"doctype": "Alms Request",
					"recipient_type": "Person",
					"recipient": person,
					"description": "Rent",
					"amount": 5,
					"status": "",
				}
			).insert(ignore_permissions=True)
		finally:
			frappe.flags.in_web_form = False
			frappe.set_user("Administrator")
		self.assertEqual(new.status, "Pending")

	def test_the_care_form_lists_the_types_and_choices(self):
		frappe.set_user(self.member)
		form = care.get_care_form()

		self.assertIn(self.category, [row["name"] for row in form["categories"]])
		self.assertIn(form["default_urgency"], form["urgencies"])

	def test_a_status_change_tells_the_owner_but_a_new_request_does_not(self):
		with patch(PUBLISH) as publish:
			request = self.make_care(self.member)
		self.assertEqual(self.portal_calls(publish), [])

		with patch(PUBLISH) as publish:
			request.status = "Triaged"
			request.save(ignore_permissions=True)

		publish.assert_any_call(
			"churchit_portal", {"topic": "care", "name": request.name}, user=self.member, after_commit=True
		)

	def test_alms_can_change_only_before_the_review(self):
		person = frappe.db.get_value("Person", {"user": self.member}, "name")
		pending = self.make_alms(self.member, person)
		reviewed = self.make_alms(self.member, person)
		frappe.db.set_value("Alms Request", reviewed.name, "status", "Approved")
		other = self.make_alms(
			self.neighbour, frappe.db.get_value("Person", {"user": self.neighbour}, "name")
		)

		frappe.set_user(self.member)
		items = {row["name"]: row for row in care.get_my_alms_requests()["items"]}

		self.assertTrue(items[pending.name]["can_change"])
		self.assertFalse(items[reviewed.name]["can_change"])
		self.assertNotIn(other.name, items)
		self.assertNotIn("associated_expense", items[pending.name])
		self.assertEqual(care.get_my_alms_requests()["me"]["name"], person)

	def test_an_alms_decision_tells_the_owner(self):
		person = frappe.db.get_value("Person", {"user": self.member}, "name")
		request = self.make_alms(self.member, person)

		with patch(PUBLISH) as publish:
			request.status = "Declined"
			request.save(ignore_permissions=True)

		publish.assert_any_call(
			"churchit_portal", {"topic": "alms", "name": request.name}, user=self.member, after_commit=True
		)

	def test_a_page_switched_off_is_refused(self):
		for route, read in (
			("care-request", care.get_my_care_requests),
			("alms-request", care.get_my_alms_requests),
		):
			self.switch_off(route)
			frappe.set_user(self.member)
			with self.assertRaises(frappe.PermissionError):
				read()
			frappe.set_user("Administrator")

	def test_recipient_search_stays_in_the_members_church(self):
		frappe.set_user(self.member)
		labels = [row["label"] for row in care.search_recipients("Person", "_Test Care")["items"]]

		self.assertIn("_Test Care _test_portal_care_b", labels)
		self.assertNotIn("_Test Care _test_portal_care_c", labels)
