# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.web_form.web_form import has_link_option

from churchit.portal.care import search_recipients
from churchit.tests.helpers import (
	ensure,
	ensure_root_church,
	ensure_user,
	make_branch,
	make_function,
	make_person,
	set_multi_church,
)


class TestPortalMembers(FrappeTestCase):
	"""A member signed in to the portal reaches their own records and names, nothing more."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		ensure_root_church()
		set_multi_church(True)
		cls.branch_a = make_branch("_Test Portal A", "TPA")
		cls.branch_b = make_branch("_Test Portal B", "TPB")
		cls.member = ensure_user("_test_portal_member@example.com", "PortalMember")
		cls.own = make_person("_Test Portal", "Member", church=cls.branch_a, user=cls.member)
		cls.neighbour = make_person("_Test Portal", "Neighbour", church=cls.branch_a).name
		cls.stranger = make_person("_Test Portal", "Stranger", church=cls.branch_b).name
		cls.addClassCleanup(frappe.clear_cache)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_member_reaches_only_their_own_person(self):
		frappe.set_user(self.member)
		self.assertEqual(frappe.get_list("Person", pluck="name"), [self.own.name])
		self.assertTrue(frappe.has_permission("Person", "write", doc=self.own.name))
		self.assertFalse(frappe.has_permission("Person", "read", doc=self.neighbour))
		self.assertFalse(frappe.has_permission("Background Check", "read"))

	def test_a_member_changes_only_what_personal_details_offers(self):
		ensure("Member Status", {"status": "Inactive"})
		frappe.set_user(self.member)
		person = frappe.get_doc("Person", self.own.name)
		person.alergies = "_Test Peanuts"
		person.hide_from_directory = 1
		person.save()

		person.membership_status = "Inactive"
		with self.assertRaises(frappe.PermissionError):
			person.save()

	def test_a_member_neither_reads_nor_changes_their_medical_notes(self):
		frappe.db.set_value("Person", self.own.name, "medical_notes", "_Test Private")
		frappe.set_user(self.member)
		person = frappe.get_doc("Person", self.own.name)
		person.medical_notes = "_Test Changed"
		person.save()
		self.assertEqual(frappe.db.get_value("Person", self.own.name, "medical_notes"), "_Test Private")

		person.reload()
		person.apply_fieldlevel_read_permissions()
		self.assertIsNone(person.get("medical_notes"))

	def test_a_member_cannot_add_a_person(self):
		"""A save that the member's own sign-in or household page did not make adds no one."""
		frappe.set_user(self.member)
		before = frappe.db.count("Person")

		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "Person", "first_name": "_Test", "last_name": "Newcomer"}).insert()
		self.assertEqual(frappe.db.count("Person"), before)

	def test_the_recipient_search_offers_names_from_the_members_church(self):
		frappe.set_user(self.member)
		results = search_recipients("Person", "_Test Portal")["items"]
		self.assertEqual({row.name for row in results}, {self.own.name, self.neighbour})
		self.assertEqual(set(results[0]), {"name", "label"})

	def test_a_request_may_not_name_a_recipient_outside_the_members_church(self):
		prayer_type = ensure("Prayer Request Type", {"type": "_Test Portal Prayer"})
		ensure("Prayer Request Status", {"status": "Requested"})
		frappe.set_user(self.member)
		function = make_function("_Test Portal Not A Recipient", church=self.branch_a).name
		for recipient_type, recipient in (("Person", self.stranger), ("Function", function)):
			with self.assertRaises(frappe.PermissionError):
				self.prayer_request(prayer_type, recipient_type, recipient)

		request = self.prayer_request(prayer_type, "Person", self.neighbour, requestor=self.stranger)
		self.assertEqual(request.requestor, self.own.name)

	def prayer_request(self, prayer_type, recipient_type, recipient, **values):
		return frappe.get_doc(
			{
				"doctype": "Prayer Request",
				"title": "_Test Portal Request",
				"type": prayer_type,
				"recipient_type": recipient_type,
				"recipient": recipient,
				**values,
			}
		).insert()

	def test_a_member_cannot_sign_up_for_another_churchs_function(self):
		theirs = make_function("_Test Portal Elsewhere", church=self.branch_b, allow_sign_ups=1).name

		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc(
				{"doctype": "Function Sign-Up", "function": theirs, "person": self.own.name}
			).insert()

	def test_no_member_form_links_to_person(self):
		"""A web form renders every name of a linked doctype it may list, hidden fields included."""
		forms = frappe.get_all(
			"Web Form", filters={"login_required": 1, "module": ("like", "Church%")}, pluck="name"
		)
		linking = [
			name
			for name in forms
			if has_link_option(frappe.get_doc("Web Form", name).web_form_fields, "Person")
		]
		self.assertEqual(linking, [])

	def test_no_guest_form_links_to_a_church_or_person(self):
		"""A guest form renders every record of a linked doctype, unpublished churches included."""
		forms = frappe.get_all(
			"Web Form", filters={"login_required": 0, "module": ("like", "Church%")}, pluck="name"
		)
		linking = [
			name
			for name in forms
			if any(
				has_link_option(frappe.get_doc("Web Form", name).web_form_fields, doctype)
				for doctype in ("Church", "Person")
			)
		]
		self.assertEqual(linking, [])

	def test_staff_are_untouched(self):
		self.assertIn(self.neighbour, frappe.get_list("Person", pluck="name"))
