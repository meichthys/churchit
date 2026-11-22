# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.utils import set_request

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

	def person_of(self, user):
		return frappe.db.get_value("Person", {"user": user}, "name")


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

	def test_the_prayer_list_puts_urgent_requests_first_and_says_who_may_see_each(self):
		calm = make_prayer_request(self.neighbour, "_Test Calm")
		urgent = make_prayer_request(self.neighbour, "_Test Urgent", urgent=1)

		frappe.set_user(self.member)
		rows = [
			row for row in care.get_community_requests()["items"] if row["name"] in (calm.name, urgent.name)
		]

		self.assertEqual([row["name"] for row in rows], [urgent.name, calm.name])
		self.assertEqual([row["visibility"] for row in rows], ["Whole Church", "Whole Church"])

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

	def test_praying_and_a_comment_tell_the_person_who_asked_not_the_login_that_saved_it(self):
		asker = frappe.db.get_value("Person", {"user": self.neighbour})
		request = make_prayer_request(
			"Administrator", "_Test Asked For", requestor=asker, church=self.church, approved_for_list=1
		)

		frappe.set_user(self.member)
		for action in (
			lambda: create_prayer(request.name, "Lord, help"),
			lambda: care.add_prayer_comment(request.name, "Praying for you"),
		):
			with patch(PUBLISH) as publish:
				action()

			users = {call.kwargs.get("user") for call in publish.call_args_list}
			self.assertIn(self.neighbour, users)
			self.assertNotIn("Administrator", users)

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

	def test_an_empty_comment_or_an_email_address_is_refused(self):
		request = make_prayer_request(self.neighbour, "_Test Address")
		frappe.set_user(self.member)

		for comment in ("   ", "someone@example.com"):
			with self.assertRaises(frappe.ValidationError):
				care.add_prayer_comment(request.name, comment)
		self.assertEqual(care.get_community_request(request.name)["comments"], [])

	def test_a_member_posts_only_a_few_comments_an_hour_on_every_request_together(self):
		"""Frappe's limit on website comments: five an hour from one address."""
		shared = make_prayer_request(self.neighbour, "_Test Many")
		own = make_prayer_request(self.member, "_Test Own Many", visibility="Private")
		saved_ip = frappe.local.request_ip
		self.addCleanup(setattr, frappe.local, "request_ip", saved_ip)
		self.addCleanup(setattr, frappe.local, "request", None)
		set_request(method="POST", path="/api/method/churchit.portal.care.add_prayer_comment")
		frappe.local.request_ip = f"_test-care-{frappe.generate_hash(length=8)}"
		frappe.set_user(self.member)

		for count in range(5):
			care.add_prayer_comment(shared.name, f"Praying, day {count}")
		with self.assertRaises(frappe.RateLimitExceededError):
			care.add_request_comment("prayer-request", own.name, "Thank you all")

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

	def test_only_the_comment_pages_are_accepted(self):
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

	def test_staff_who_use_the_app_keep_the_status_the_care_team_set(self):
		staff = add_member("_test_portal_care_staff@example.com", self.church, "Church Manager")
		person = self.person_of(staff)
		frappe.set_user(staff)
		need = {"category": self.category, "description": "_Test staff need"}
		help_for_me = {"recipient_type": "Person", "recipient": person, "description": "Rent", "amount": 5}

		request = care.save_care_request(**need)["name"]
		alms = care.save_alms_request(**help_for_me)["name"]
		self.assertEqual(
			frappe.db.get_value("Alms Request", alms, ["status", "requestor"]), ("Pending", person)
		)

		frappe.db.set_value("Care Request", request, "status", "In Progress")
		frappe.db.set_value("Alms Request", alms, "status", "Approved")
		care.save_care_request(**need, name=request)
		care.save_alms_request(**{**help_for_me, "amount": 6}, name=alms)

		self.assertEqual(frappe.db.get_value("Care Request", request, "status"), "In Progress")
		self.assertEqual(frappe.db.get_value("Alms Request", alms, ["status", "amount"]), ("Approved", 6))

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

	def test_recipient_search_names_only_the_doctypes_a_request_may_name(self):
		frappe.set_user(self.member)
		for doctype in ("User", "Counseling Case"):
			with self.assertRaises(frappe.PermissionError):
				care.search_recipients(doctype, "admin")


class TestSavingRequests(CareCase):
	"""The member's own prayer, care and benevolence requests, saved through the app."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.prayer_type = ensure("Prayer Request Type", {"type": "Health"})
		cls.category = ensure("Care Request Type", {"type": "_Test Meals"})
		ensure("Prayer Request Status", {"status": "Answered"})

	def save_prayer(self, user, **values):
		frappe.set_user(user)
		values = {"title": "_Test Saved", "type": self.prayer_type, "visibility": "Whole Church", **values}
		return frappe.get_doc("Prayer Request", care.save_prayer_request(**values)["name"])

	def help_for(self, user, **values):
		"""The fields of a benevolence request *user* sends for themselves."""
		person = self.person_of(user)
		return {
			"recipient_type": "Person",
			"recipient": person,
			"description": "Rent",
			"amount": 50,
			**values,
		}

	def test_a_prayer_request_names_the_member_and_keeps_the_chosen_recipient(self):
		neighbour = self.person_of(self.neighbour)

		request = self.save_prayer(self.member, recipient_type="Person", recipient=neighbour, urgent=1)

		self.assertEqual(request.requestor, self.person_of(self.member))
		self.assertEqual(request.recipient, neighbour)
		self.assertEqual(request.recipient_name, "_Test Care _test_portal_care_b")
		self.assertEqual((request.status, request.approved_for_list, request.urgent), ("Requested", 1, 1))

	def test_a_save_takes_only_the_fields_of_the_form(self):
		"""Frappe drops what a whitelisted function does not take, so a status or requester sent along does nothing."""
		frappe.set_user(self.member)

		saved = frappe.call(
			"churchit.portal.care.save_prayer_request",
			title="_Test Sent Along",
			type=self.prayer_type,
			visibility="Private",
			status="Answered",
			approved_for_list=0,
			requestor=self.person_of(self.neighbour),
		)

		self.assertEqual(
			frappe.db.get_value(
				"Prayer Request", saved["name"], ["status", "approved_for_list", "requestor"]
			),
			("Requested", 1, self.person_of(self.member)),
		)

	def test_a_member_changes_their_own_prayer_request_and_no_one_elses(self):
		request = self.save_prayer(self.member)
		theirs = self.save_prayer(self.neighbour)

		frappe.set_user(self.member)
		care.save_prayer_request(
			title="_Test Changed", type=self.prayer_type, visibility="Private", name=request.name
		)
		self.assertEqual(
			frappe.db.get_value("Prayer Request", request.name, ["title", "visibility"]),
			("_Test Changed", "Private"),
		)

		with self.assertRaises(frappe.PermissionError):
			care.save_prayer_request(
				title="_Test Taken", type=self.prayer_type, visibility="Private", name=theirs.name
			)
		with self.assertRaises(frappe.PermissionError):
			care.delete_prayer_request(theirs.name)
		self.assertEqual(frappe.db.get_value("Prayer Request", theirs.name, "title"), "_Test Saved")

	def test_a_recipient_from_another_church_is_refused(self):
		with self.assertRaises(frappe.PermissionError):
			self.save_prayer(self.member, recipient_type="Person", recipient=self.person_of(self.stranger))

	def test_a_member_deletes_their_prayer_request_until_someone_prays_for_it(self):
		request = self.save_prayer(self.member)
		care.delete_prayer_request(request.name)
		self.assertFalse(frappe.db.exists("Prayer Request", request.name))

		prayed = self.save_prayer(self.member)
		frappe.set_user(self.neighbour)
		create_prayer(prayed.name)
		frappe.set_user(self.member)
		with self.assertRaises(frappe.LinkExistsError):
			care.delete_prayer_request(prayed.name)

	def test_a_care_request_is_for_the_member_and_its_status_stays_with_the_care_team(self):
		frappe.set_user(self.member)

		name = care.save_care_request(category=self.category, description="_Test meals", urgency="High")[
			"name"
		]
		request = frappe.get_doc("Care Request", name)
		self.assertEqual(
			(request.person, request.status, request.urgency),
			(self.person_of(self.member), "Requested", "High"),
		)

		frappe.db.set_value("Care Request", name, "status", "In Progress")
		care.save_care_request(category=self.category, description="_Test meals for two", name=name)
		self.assertEqual(
			frappe.db.get_value("Care Request", name, ["description", "status"]),
			("_Test meals for two", "In Progress"),
		)

	def test_a_member_changes_only_their_own_care_request(self):
		frappe.set_user(self.neighbour)
		theirs = care.save_care_request(category=self.category, description="_Test theirs")["name"]

		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			care.save_care_request(category=self.category, description="_Test taken", name=theirs)

	def test_a_benevolence_request_names_the_member_and_changes_only_until_it_is_reviewed(self):
		frappe.set_user(self.member)
		pending = care.save_alms_request(**self.help_for(self.member))["name"]
		reviewed = care.save_alms_request(**self.help_for(self.member, description="Food"))["name"]
		self.assertEqual(
			frappe.db.get_value("Alms Request", pending, ["requestor", "status"]),
			(self.person_of(self.member), "Pending"),
		)

		frappe.db.set_value("Alms Request", reviewed, "status", "Approved")
		with self.assertRaises(frappe.PermissionError):
			care.save_alms_request(**self.help_for(self.member, amount=500), name=reviewed)
		with self.assertRaises(frappe.PermissionError):
			care.delete_alms_request(reviewed)

		care.save_alms_request(**self.help_for(self.member, amount=60), name=pending)
		self.assertEqual(frappe.db.get_value("Alms Request", pending, "amount"), 60)
		care.delete_alms_request(pending)
		self.assertFalse(frappe.db.exists("Alms Request", pending))

	def test_a_member_cannot_change_or_delete_another_members_benevolence_request(self):
		frappe.set_user(self.neighbour)
		theirs = care.save_alms_request(**self.help_for(self.neighbour))["name"]

		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			care.save_alms_request(**self.help_for(self.member), name=theirs)
		with self.assertRaises(frappe.PermissionError):
			care.delete_alms_request(theirs)

	def test_a_login_with_no_person_is_refused(self):
		frappe.set_user(ensure_user("_test_portal_care_nobody@example.com", "Nobody"))

		with self.assertRaises(frappe.PermissionError):
			care.save_care_request(category=self.category, description="_Test nobody")
		with self.assertRaises(frappe.PermissionError):
			care.save_prayer_request(title="_Test Nobody", type=self.prayer_type, visibility="Private")

	def test_a_switched_off_page_takes_no_save_or_delete(self):
		request = self.save_prayer(self.member)
		frappe.set_user(self.member)
		alms = care.save_alms_request(**self.help_for(self.member))["name"]
		frappe.set_user("Administrator")
		for route in ("prayer-request", "care-request", "alms-request"):
			self.switch_off(route)

		frappe.set_user(self.member)
		for save in (
			lambda: care.save_prayer_request(title="_Test Off", type=self.prayer_type, visibility="Private"),
			lambda: care.delete_prayer_request(request.name),
			lambda: care.save_care_request(category=self.category, description="_Test off"),
			lambda: care.save_alms_request(**self.help_for(self.member)),
			lambda: care.delete_alms_request(alms),
		):
			with self.assertRaises(frappe.PermissionError):
				save()
