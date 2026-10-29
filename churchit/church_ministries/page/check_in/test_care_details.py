# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.permissions import setup_custom_perms

from churchit.church_ministries.page.check_in.check_in import (
	CARE_FIELDS,
	add_visitor,
	find_card_holder,
	search_people,
)
from churchit.tests.helpers import RollbackEachTest, ensure, ensure_user, make_person

NOTES = "Carries an inhaler"
CONTACT = ("Nan _Test Caredetail", "+1 555 010 3333")


def grant(doctype, role, ptype):
	"""Add a Custom DocPerm without Frappe's whole-doctype check, which refuses Person's shipped levels."""
	setup_custom_perms(doctype)
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			ptype: 1,
		}
	).insert(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype)


class TestCareDetailsAtTheStation(RollbackEachTest):
	"""The station shows allergies and grade to its users, and medical notes and emergency contacts at permlevel 1."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.child = make_person(
			"Mila",
			"_Test Caredetail",
			alergies="Peanuts",
			medical_notes=NOTES,
			graduation_year=frappe.utils.getdate().year + 8,
			emergency_contact_name=CONTACT[0],
			emergency_contact_phone=CONTACT[1],
		)
		cls.volunteer = ensure_user(
			"_test_care_volunteer@example.com", "CareVolunteer", roles=("Church Check-In",)
		)

	def found(self, query="_Test Caredetail"):
		(group,) = search_people(query)
		(member,) = group["members"]
		return member

	def test_a_check_in_volunteer_sees_grade_allergies_medical_notes_and_emergency_contact(self):
		frappe.set_user(self.volunteer)
		member = self.found()

		self.assertTrue(member.grade)
		self.assertEqual(member.grade, frappe.db.get_value("Person", self.child.name, "grade"))
		self.assertEqual(
			(
				member.alergies,
				member.medical_notes,
				member.emergency_contact_name,
				member.emergency_contact_phone,
			),
			("Peanuts", NOTES, *CONTACT),
		)

	def test_a_reader_without_permlevel_1_gets_no_medical_notes_or_emergency_contact(self):
		role = ensure("Role", {"role_name": "_Test Check-In Helper"})
		grant("Person", role, "read")
		grant("Function Check-In", role, "create")
		for doctype in ("Person", "Function Check-In"):
			self.addCleanup(frappe.clear_cache, doctype=doctype)
		helper = ensure_user("_test_care_helper@example.com", "CareHelper", roles=(role,))

		frappe.set_user(helper)
		self.assertTrue(frappe.has_permission("Function Check-In", "create"))
		member = self.found()

		self.assertEqual((member.alergies, member.grade), ("Peanuts", self.child.grade))
		for fieldname in CARE_FIELDS:
			self.assertNotIn(fieldname, member)

	def test_readers_without_the_station_right_are_refused(self):
		staff = ensure_user("_test_care_staff@example.com", "CareStaff", roles=("Church Staff",))
		member = ensure_user("_test_care_member@example.com", "CareMember", roles=("Church User",))

		for user in (staff, member):
			frappe.set_user(user)
			self.assertTrue(frappe.has_permission("Person"))
			with self.assertRaises(frappe.PermissionError):
				search_people("_Test Caredetail")
			with self.assertRaises(frappe.PermissionError):
				find_card_holder(self.child.name)

	def test_add_visitor_stores_an_emergency_contact(self):
		frappe.set_user(self.volunteer)
		visitor = add_visitor(
			"Otto",
			"_Test Caredetail Visitor",
			emergency_contact_name=CONTACT[0],
			emergency_contact_phone=CONTACT[1],
		)

		self.assertEqual(
			frappe.db.get_value(
				"Person", visitor["name"], ["emergency_contact_name", "emergency_contact_phone"]
			),
			CONTACT,
		)
		self.assertEqual(self.found("Otto")["emergency_contact_name"], CONTACT[0])
