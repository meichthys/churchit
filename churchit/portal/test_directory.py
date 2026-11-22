# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.portal.directory import get_directory
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_person, make_two_churches


class TestPortalDirectory(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, church, other_church = make_two_churches()
		frappe.db.set_single_value("People Settings", "member_directory", 1)
		cls.member = ensure_user("_test_portal_dir_member@example.com", "Member")
		make_person("_Test Dir", "Member", church=church, user=cls.member, share_email=0)
		make_person("_Test Dir", "Neighbour", church=church, share_email=0)
		make_person("_Test Dir", "Stranger", church=other_church)
		cls.visitor = ensure_user("_test_portal_dir_visitor@example.com", "Visitor")
		make_person("_Test Dir", "Visitor", church=church, user=cls.visitor, membership="Visitor")
		cls.loner = ensure_user("_test_portal_dir_loner@example.com", "Loner")

	def titles(self):
		return [entry["title"] for entry in get_directory()["entries"]]

	def test_a_member_sees_their_own_church_only(self):
		frappe.set_user(self.member)
		titles = self.titles()

		self.assertIn("Neighbour, _Test Dir", titles)
		self.assertNotIn("Stranger, _Test Dir", titles)
		self.assertEqual(get_directory()["status"], "ok")

	def test_an_entry_carries_no_person_id(self):
		frappe.set_user(self.member)
		entry = get_directory()["entries"][0]

		self.assertEqual(
			set(entry),
			{"name", "title", "photo", "emails", "phones", "addresses", "birthdays", "vcard", "search"},
		)

	def test_a_visitor_is_told_they_are_not_a_member(self):
		frappe.set_user(self.visitor)

		self.assertEqual(get_directory(), {"status": "not_member", "entries": []})

	def test_a_login_without_a_person_is_refused(self):
		frappe.set_user(self.loner)

		with self.assertRaises(frappe.PermissionError):
			get_directory()

	def test_a_guest_is_refused(self):
		frappe.set_user("Guest")

		with self.assertRaises(frappe.PermissionError):
			get_directory()

	def test_the_directory_is_not_found_until_it_is_on(self):
		frappe.db.set_single_value("People Settings", "member_directory", 0)
		frappe.set_user(self.member)

		with self.assertRaises(frappe.DoesNotExistError):
			get_directory()

	def test_a_page_switched_off_is_refused(self):
		features = frappe.get_single("Church Features")
		features.get("website_pages", {"route": "directory"})[0].enabled = 0
		features.save()
		frappe.set_user(self.member)

		with self.assertRaises(frappe.PermissionError):
			get_directory()
