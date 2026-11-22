# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from unittest.mock import patch

import frappe
from frappe.exceptions import PermissionError, ValidationError

from churchit.church_study.doctype.bible_memory_item.bible_memory_item import (
	assign_memory,
	complete_session,
	record_mistake,
)
from churchit.church_website.pages import sync_page_switches
from churchit.portal import faith
from churchit.portal.test_boot import switch_page
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	make_function,
	make_person,
	make_translation,
	make_two_churches,
)

REFERENCE = "John 1:1"
PUBLISH = "churchit.portal.realtime.frappe.publish_realtime"


class FaithTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.church_a, cls.church_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		sync_page_switches()
		cls.translation = make_translation(
			cls, "_TFH", [("JHN", 1, 1, "In the beginning was the Word and the Word was with God.")]
		)
		cls.member = ensure_user("_test_faith_member@example.com", "Faith")
		cls.other = ensure_user("_test_faith_other@example.com", "Other")
		cls.manager = ensure_user("_test_faith_manager@example.com", "Manager", ("Church Manager",))
		cls.no_person = ensure_user("_test_faith_nobody@example.com", "Nobody")
		for email, church in (
			(cls.member, cls.church_a),
			(cls.other, cls.church_b),
			(cls.manager, cls.church_a),
		):
			make_person("_Test Faith", email.split("_")[3], church=church, user=email)

	def make_item(self, user=None, **values):
		return frappe.get_doc(
			{
				"doctype": "Bible Memory Item",
				"bible_reference": REFERENCE,
				"translation": self.translation,
				"user": user or self.member,
				**values,
			}
		).insert(ignore_permissions=True)

	def assign_to_member(self):
		frappe.set_user(self.manager)
		assign_memory(REFERENCE, self.translation, users=[self.member])
		frappe.set_user(self.member)
		return frappe.db.get_value("Bible Memory Item", {"user": self.member, "bible_reference": REFERENCE})


class TestMemoryList(FaithTestCase):
	def test_lists_the_members_own_passages_with_a_preview_and_the_choices(self):
		mine = self.make_item(progress=40)
		self.make_item(self.other)
		frappe.set_user(self.member)

		result = faith.get_memory_list()

		self.assertEqual([item["name"] for item in result["items"]], [mine.name])
		item = result["items"][0]
		self.assertEqual(item["progress"], 40)
		self.assertTrue(item["preview"].startswith("In the beginning"))
		self.assertIn(self.translation, result["translations"])

	def test_a_manager_lists_only_their_own_passages_too(self):
		self.make_item(self.member)
		frappe.set_user(self.manager)

		self.assertEqual(faith.get_memory_list()["items"], [])

	def test_shows_who_assigned_a_passage(self):
		self.assign_to_member()

		item = faith.get_memory_list()["items"][0]

		self.assertEqual(item["assigned_by_name"], "Manager")

	def test_a_translation_with_no_text_gets_no_preview_and_no_download(self):
		frappe.db.set_value("Bible Translation", self.translation, "status", "No Text")
		frappe.clear_document_cache("Bible Translation", self.translation)
		self.make_item()
		frappe.set_user(self.member)

		with patch("churchit.scripture.download_now") as download:
			item = faith.get_memory_list()["items"][0]

		self.assertIsNone(item["preview"])
		download.assert_not_called()

	def test_refuses_a_guest_a_login_with_no_person_and_a_switched_off_page(self):
		for user in ("Guest", self.no_person):
			frappe.set_user(user)
			with self.assertRaises(PermissionError):
				faith.get_memory_list()

		frappe.set_user("Administrator")
		switch_page("memorize", 0)
		frappe.set_user(self.member)
		with self.assertRaises(PermissionError):
			faith.get_memory_list()


class TestAddAndRemove(FaithTestCase):
	def test_adds_a_passage_for_the_member_and_tidies_the_reference(self):
		frappe.set_user(self.member)

		result = faith.add_memory_item("jn 1:1", self.translation)

		item = frappe.get_doc("Bible Memory Item", result["name"])
		self.assertEqual((item.user, item.bible_reference, item.assigned_by), (self.member, REFERENCE, None))

	def test_refuses_a_reference_that_cannot_be_read_and_a_duplicate(self):
		frappe.set_user(self.member)
		with self.assertRaises(ValidationError):
			faith.add_memory_item("not a verse at all", self.translation)

		faith.add_memory_item(REFERENCE, self.translation)
		with self.assertRaises(ValidationError):
			faith.add_memory_item(REFERENCE, self.translation)

	def test_refuses_a_translation_that_is_not_readable(self):
		frappe.db.set_value("Bible Translation", self.translation, "status", "Failed")
		frappe.clear_document_cache("Bible Translation", self.translation)
		frappe.set_user(self.member)

		with self.assertRaises(PermissionError):
			faith.add_memory_item(REFERENCE, self.translation)

	def test_removes_an_own_and_an_assigned_passage(self):
		own = self.make_item(self.member, bible_reference="John 1:2")
		assigned = self.assign_to_member()
		frappe.set_user(self.member)

		faith.remove_memory_item(own.name)
		faith.remove_memory_item(assigned)

		self.assertFalse(frappe.db.exists("Bible Memory Item", {"user": self.member}))

	def test_refuses_removing_another_members_passage(self):
		theirs = self.make_item(self.other)
		frappe.set_user(self.member)

		with self.assertRaises(PermissionError):
			faith.remove_memory_item(theirs.name)

		self.assertTrue(frappe.db.exists("Bible Memory Item", theirs.name))

	def test_a_manager_cannot_remove_through_the_app_what_is_not_theirs(self):
		theirs = self.make_item(self.member)
		frappe.set_user(self.manager)

		with self.assertRaises(PermissionError):
			faith.remove_memory_item(theirs.name)


class TestAssignedPassage(FaithTestCase):
	def test_a_member_practices_a_passage_a_manager_assigned(self):
		name = self.assign_to_member()

		practice = faith.get_practice(name)
		mistake = record_mistake(name, 0)
		finished = complete_session(name, "type", 1, [0, 1])

		self.assertEqual(practice["text"], "In the beginning was the Word and the Word was with God.")
		self.assertEqual(mistake["progress"], 0)
		self.assertEqual(finished["progress"], 10)

	def test_assigning_tells_each_assignee_to_read_the_list_again(self):
		frappe.set_user(self.manager)

		with patch(PUBLISH) as publish:
			assign_memory(REFERENCE, self.translation, users=[self.member])

		name = frappe.db.get_value("Bible Memory Item", {"user": self.member})
		publish.assert_any_call(
			"churchit_portal", {"topic": "memory", "name": name}, user=self.member, after_commit=True
		)

	def test_a_member_never_reads_another_members_item(self):
		theirs = self.make_item(self.other)
		frappe.set_user(self.member)

		for call in (lambda: faith.get_practice(theirs.name), lambda: record_mistake(theirs.name, 0)):
			with self.assertRaises(PermissionError):
				call()

	def test_a_manager_has_no_practice_of_a_members_item(self):
		theirs = self.make_item(self.member)
		frappe.set_user(self.manager)

		with self.assertRaises(PermissionError):
			faith.get_practice(theirs.name)

	def test_the_list_hides_other_members_items_from_a_member_and_from_a_staff_login(self):
		self.make_item(self.other)
		staff = ensure_user("_test_faith_staff@example.com", "Staff", ("Church Staff",))

		for user in (self.member, staff):
			frappe.set_user(user)
			self.assertEqual(frappe.get_list("Bible Memory Item", filters={"user": self.other}), [])

	def test_practice_refuses_text_that_is_not_readable(self):
		item = self.make_item()
		frappe.db.set_value("Bible Translation", self.translation, "status", "Failed")
		frappe.clear_document_cache("Bible Translation", self.translation)
		frappe.set_user(self.member)

		with self.assertRaises(ValidationError):
			faith.get_practice(item.name)

	def test_a_member_cannot_take_over_another_users_item_with_set_value(self):
		theirs = self.make_item(self.other)
		frappe.set_user(self.member)

		with self.assertRaises(PermissionError):
			frappe.client.set_value("Bible Memory Item", theirs.name, "user", self.member)

		self.assertEqual(frappe.db.get_value("Bible Memory Item", theirs.name, "user"), self.other)

	def test_a_manager_can_still_change_the_user_of_an_item(self):
		item = self.make_item(self.other)
		frappe.set_user(self.manager)

		frappe.client.set_value("Bible Memory Item", item.name, "user", self.member)

		self.assertEqual(frappe.db.get_value("Bible Memory Item", item.name, "user"), self.member)

	def test_the_list_names_each_translation(self):
		frappe.set_user(self.member)

		titles = faith.get_memory_list()["translation_titles"]

		self.assertIn(self.translation, titles)


class TestBulletins(FaithTestCase):
	def make_bulletin(self, function_name, church, publish=1):
		function = make_function(function_name, church=church)
		return frappe.get_doc({"doctype": "Bulletin", "function": function.name, "publish": publish}).insert(
			ignore_permissions=True
		)

	def test_lists_this_churchs_published_bulletins_with_both_links(self):
		for church in (self.church_a, self.church_b):
			frappe.db.set_value("Church", church, "publish", 1)
		mine = self.make_bulletin("_Test Faith Mine", self.church_a)
		self.make_bulletin("_Test Faith Theirs", self.church_b)
		self.make_bulletin("_Test Faith Draft", self.church_a, publish=0)
		frappe.set_user(self.member)

		items = faith.get_bulletins()["items"]

		self.assertEqual([item["name"] for item in items], [mine.name])
		self.assertEqual(items[0]["digital_url"], f"/bulletins?name={mine.name}")
		self.assertIn(f"download_pdf?name={mine.name}", items[0]["pdf_url"])

	def test_refuses_a_guest_and_a_switched_off_page(self):
		frappe.set_user("Guest")
		with self.assertRaises(PermissionError):
			faith.get_bulletins()

		frappe.set_user("Administrator")
		switch_page("bulletins", 0)
		frappe.set_user(self.member)
		with self.assertRaises(PermissionError):
			faith.get_bulletins()
