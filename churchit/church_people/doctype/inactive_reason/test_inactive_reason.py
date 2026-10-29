# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.doctype.inactive_reason.inactive_reason import (
	DECEASED,
	TRANSFERRED,
	create_inactive_reasons,
)
from churchit.patches.v1_0 import add_inactive_reasons
from churchit.tests.helpers import ensure, make_person


class TestInactiveReason(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_inactive_reasons()

	def test_the_reasons_the_app_sets_cannot_be_deleted(self):
		for reason in (DECEASED, TRANSFERRED):
			with self.assertRaises(frappe.ValidationError, msg=reason):
				frappe.delete_doc("Inactive Reason", reason)
			self.assertTrue(frappe.db.exists("Inactive Reason", reason))

	def test_the_reasons_the_app_sets_cannot_be_renamed(self):
		for reason in (DECEASED, TRANSFERRED):
			with self.assertRaises(frappe.ValidationError, msg=reason):
				frappe.rename_doc("Inactive Reason", reason, f"_Test {reason}")
			self.assertTrue(frappe.db.exists("Inactive Reason", reason))

	def test_a_church_s_own_reason_can_be_renamed(self):
		ensure("Inactive Reason", {"reason": "_Test Moved Awya"})

		frappe.rename_doc("Inactive Reason", "_Test Moved Awya", "_Test Moved Away")

		self.assertEqual(
			frappe.db.get_value("Inactive Reason", "_Test Moved Away", "reason"), "_Test Moved Away"
		)


class TestCreateInactiveReasons(FrappeTestCase):
	"""Inactive Reason on Person was free text, so every value stored there needs a record."""

	def store_reason(self, first_name, reason):
		"""A person holding *reason* as the free text the field used to take."""
		person = make_person(first_name, membership_status="Inactive")
		frappe.db.set_value("Person", person.name, "inactive_reason", reason)
		return person

	def test_every_stored_reason_becomes_a_record(self):
		self.store_reason("_Test Legacy One", "_Test Joined the Navy")
		padded = self.store_reason("_Test Legacy Two", " _Test Moved Abroad ")

		add_inactive_reasons.execute()

		for reason in (DECEASED, TRANSFERRED, "_Test Joined the Navy", "_Test Moved Abroad"):
			self.assertTrue(frappe.db.exists("Inactive Reason", reason), reason)
		self.assertEqual(frappe.db.get_value("Person", padded.name, "inactive_reason"), "_Test Moved Abroad")

	def test_a_stored_reason_links_once_it_has_a_record(self):
		person = self.store_reason("_Test Legacy Three", "_Test Went Overseas")

		create_inactive_reasons()

		person.reload()
		person.notes = "Saved after the change to a link."
		person.save()
		self.assertEqual(person.inactive_reason, "_Test Went Overseas")

	def test_a_stored_reason_frappe_refuses_as_a_name_is_tidied_on_the_person_too(self):
		tidied = {
			"_Test <Moved> away": "_Test Moved away",
			"_Test Age > 90": "_Test Age 90",
			"_Test Left\ntown\tquietly": "_Test Left town quietly",
			"<>": None,
			"   ": None,
		}
		people = {
			text: self.store_reason(f"_Test Legacy Odd {i}", text).name for i, text in enumerate(tidied)
		}

		add_inactive_reasons.execute()

		for text, reason in tidied.items():
			self.assertEqual(frappe.db.get_value("Person", people[text], "inactive_reason"), reason, text)
			# A save checks the link.
			frappe.get_doc("Person", people[text]).save()

	def test_running_again_and_differing_case_add_nothing(self):
		self.store_reason("_Test Legacy Four", "_Test Left Town")
		self.store_reason("_Test Legacy Five", "_test left town")

		create_inactive_reasons()
		create_inactive_reasons()

		self.assertEqual(frappe.db.count("Inactive Reason", {"reason": ("like", "_test left town")}), 1)
