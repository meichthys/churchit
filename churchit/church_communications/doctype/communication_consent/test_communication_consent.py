# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_communications.doctype.communication_consent.communication_consent import (
	EMAIL,
	GIVEN,
	WITHDRAWN,
	record,
)
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHURCH_NEWS,
	create_communication_purposes,
)
from churchit.tests.helpers import (
	RollbackEachTest,
	assert_scoped,
	ensure_root_church,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)


class TestCommunicationConsent(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		ensure_root_church()
		create_communication_purposes()
		cls.person = make_person("_Test Set Once", "Consent")

	def test_a_recorded_answer_cannot_be_changed(self):
		(name,) = record([self.person.name], EMAIL, GIVEN, CHURCH_NEWS)
		for field, value in (("status", WITHDRAWN), ("channel", "SMS"), ("purpose", None)):
			consent = frappe.get_doc("Communication Consent", name)
			consent.set(field, value)
			with self.subTest(field), self.assertRaises(frappe.CannotChangeConstantError):
				consent.save()

	def test_notes_can_still_be_added(self):
		(name,) = record([self.person.name], EMAIL, GIVEN)
		consent = frappe.get_doc("Communication Consent", name)
		consent.notes = "Said so at the welcome desk."
		consent.save()
		self.assertEqual(frappe.db.get_value("Communication Consent", name, "notes"), consent.notes)


class TestCommunicationConsentPerChurch(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		create_communication_purposes()
		cls.manager_a = ensure_user(
			"_test_consent_manager_a@example.com", "ConsentA", roles=("Church Manager",)
		)
		make_person("_Test Consent Manager", "A", church=cls.branch_a, user=cls.manager_a)
		cls.person_a = make_person("_Test Consent Scope", "A", church=cls.branch_a).name
		cls.person_b = make_person("_Test Consent Scope", "B", church=cls.branch_b).name

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_a_consent_takes_its_persons_church(self):
		(name,) = record([self.person_b], EMAIL, GIVEN)
		self.assertEqual(frappe.db.get_value("Communication Consent", name, "church"), self.branch_b)

	def test_a_church_sees_only_its_own_peoples_consent(self):
		(mine,) = record([self.person_a], EMAIL, GIVEN)
		(theirs,) = record([self.person_b], EMAIL, GIVEN)
		assert_scoped(self, "Communication Consent", self.manager_a, mine, theirs)

	def test_a_church_cannot_record_consent_for_another_churchs_person(self):
		frappe.set_user(self.manager_a)
		consent = frappe.get_doc(
			{
				"doctype": "Communication Consent",
				"person": self.person_b,
				"channel": EMAIL,
				"status": WITHDRAWN,
			}
		)
		with self.assertRaises(frappe.PermissionError):
			consent.insert()
