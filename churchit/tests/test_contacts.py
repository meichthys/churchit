# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.exceptions import PermissionError, ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.contacts import (
	create_default_contact_types,
	get_emails_for,
	get_mailing_address,
	get_primary_address,
	get_primary_email,
	get_primary_emails,
	get_primary_phone,
	mailing_address,
	pick,
	primary_address,
	primary_email,
	primary_email_query,
	primary_phone,
	primary_phone_query,
)
from churchit.tests.helpers import ensure_user, make_address, make_person


class TestPick(FrappeTestCase):
	"""Reading contact values off an in-memory document."""

	def _person(self, emails=(), phones=(), addresses=()):
		person = frappe.new_doc("Person")
		for email, is_primary in emails:
			person.append("emails", {"email_address": email, "is_primary": is_primary})
		for phone, is_primary in phones:
			person.append("phones", {"phone_number": phone, "is_primary": is_primary})
		for address, is_primary, is_mailing in addresses:
			person.append(
				"addresses", {"address": address, "is_primary": is_primary, "is_mailing_address": is_mailing}
			)
		return person

	def test_pick_prefers_the_flagged_row_then_the_first(self):
		rows = [frappe._dict(value="a", is_primary=0), frappe._dict(value="b", is_primary=1)]
		self.assertEqual(pick(rows, "value"), "b")
		self.assertEqual(pick([frappe._dict(value="a", is_primary=0)], "value"), "a")
		self.assertIsNone(pick([], "value"))

	def test_primary_helpers_read_the_flagged_rows(self):
		person = self._person(
			emails=[("one@example.com", 0), ("two@example.com", 1)],
			phones=[("111", 1), ("222", 0)],
			addresses=[("ADDR-1", 1, 0), ("ADDR-2", 0, 1)],
		)
		self.assertEqual(primary_email(person), "two@example.com")
		self.assertEqual(primary_phone(person), "111")
		self.assertEqual(primary_address(person), "ADDR-1")
		self.assertEqual(mailing_address(person), "ADDR-2")

	def test_mailing_address_falls_back_to_the_primary(self):
		self.assertEqual(mailing_address(self._person(addresses=[("ADDR-1", 1, 0)])), "ADDR-1")
		self.assertIsNone(mailing_address(self._person()))


class TestContactLookups(FrappeTestCase):
	"""Lookups and report subqueries against saved records."""

	def setUp(self):
		self.home = make_address("_Test Home").name
		self.box = make_address("_Test PO Box").name
		self.person = make_person("_Test Lookup", "Person")
		self.person.append("emails", {"email_address": "work@example.com"})
		self.person.append("emails", {"email_address": "home@example.com", "is_primary": 1})
		self.person.append("phones", {"phone_number": "555-0100", "is_primary": 1})
		self.person.append("addresses", {"address": self.home, "is_primary": 1})
		self.person.append("addresses", {"address": self.box, "is_mailing_address": 1})
		self.person.save(ignore_permissions=True)
		self.emailless = make_person("_Test Lookup", "Emailless")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_single_record_lookups(self):
		self.assertEqual(get_primary_email("Person", self.person.name), "home@example.com")
		self.assertEqual(get_primary_phone("Person", self.person.name), "555-0100")
		self.assertEqual(get_primary_address("Person", self.person.name), self.home)
		self.assertEqual(get_mailing_address("Person", self.person.name), self.box)
		self.assertIsNone(get_primary_email("Person", self.emailless.name))
		self.assertIsNone(get_primary_email("Person", None))

	def test_mailing_lookup_falls_back_to_primary(self):
		person = make_person("_Test Lookup", "Home Only")
		person.append("addresses", {"address": self.home})
		person.save(ignore_permissions=True)
		self.assertEqual(get_mailing_address("Person", person.name), self.home)

	def test_bulk_email_map_skips_records_without_email(self):
		by_person = get_primary_emails("Person", [self.person.name, self.emailless.name, None])
		self.assertEqual(by_person, {self.person.name: "home@example.com"})
		self.assertEqual(get_primary_emails("Person", []), {})

	def test_report_subqueries_resolve_the_primary_value(self):
		Person = frappe.qb.DocType("Person")
		row = (
			frappe.qb.from_(Person)
			.select(
				primary_email_query(Person).as_("email"),
				primary_phone_query(Person).as_("phone"),
			)
			.where(Person.name == self.person.name)
			.run(as_dict=True)
		)[0]
		self.assertEqual(row.email, "home@example.com")
		self.assertEqual(row.phone, "555-0100")

	def test_subqueries_reject_doctypes_without_contact_tables(self):
		with self.assertRaises(ValidationError):
			primary_email_query(frappe.qb.DocType("User"), parenttype="User")

	def test_get_emails_for_returns_found_and_missing(self):
		result = get_emails_for("Person", frappe.as_json([self.person.name, self.emailless.name]))
		self.assertEqual(result, {"emails": ["home@example.com"], "missing": [self.emailless.name]})

	def test_get_emails_for_enforces_read_permission(self):
		frappe.set_user(ensure_user("_test_contact_nobody@example.com", "_Test Nobody", roles=()))
		with self.assertRaises(PermissionError):
			get_emails_for("Person", [self.person.name])

	def test_get_emails_for_rejects_other_doctypes(self):
		with self.assertRaises(ValidationError):
			get_emails_for("User", ["Administrator"])


class TestValidateContactTables(FrappeTestCase):
	"""The normalisation every contact-carrying doctype runs in validate()."""

	def _person(self, name, emails=(), addresses=()):
		person = make_person("_Test Validate", name)
		for row in emails:
			person.append("emails", row)
		for row in addresses:
			person.append("addresses", row)
		person.save(ignore_permissions=True)
		return person

	def test_values_are_trimmed(self):
		person = self._person("Trim", emails=[{"email_address": "  padded@example.com  "}])
		self.assertEqual(person.emails[0].email_address, "padded@example.com")

	def test_duplicates_are_rejected_case_insensitively(self):
		with self.assertRaises(ValidationError):
			self._person(
				"Dupe",
				emails=[{"email_address": "same@example.com"}, {"email_address": "SAME@example.com"}],
			)

	def test_first_row_becomes_primary_when_none_is_flagged(self):
		person = self._person(
			"Default", emails=[{"email_address": "a@example.com"}, {"email_address": "b@example.com"}]
		)
		self.assertEqual([row.is_primary for row in person.emails], [1, 0])

	def test_newly_ticked_row_wins_over_the_previous_primary(self):
		person = self._person(
			"Switch",
			emails=[{"email_address": "a@example.com", "is_primary": 1}, {"email_address": "b@example.com"}],
		)
		# Tick the second row without unticking the first, as a portal form would.
		person.emails[1].is_primary = 1
		person.save(ignore_permissions=True)
		self.assertEqual([row.is_primary for row in person.emails], [0, 1])

	def test_last_flagged_row_wins_on_a_new_record(self):
		person = self._person(
			"Both",
			emails=[
				{"email_address": "a@example.com", "is_primary": 1},
				{"email_address": "b@example.com", "is_primary": 1},
			],
		)
		self.assertEqual([row.is_primary for row in person.emails], [0, 1])

	def test_mailing_flag_is_single_but_not_defaulted(self):
		home = make_address("_Test Validate Home").name
		box = make_address("_Test Validate Box").name
		person = self._person("Mail", addresses=[{"address": home}, {"address": box}])
		self.assertEqual([row.is_mailing_address for row in person.addresses], [0, 0])

		person.addresses[0].is_mailing_address = 1
		person.addresses[1].is_mailing_address = 1
		person.save(ignore_permissions=True)
		self.assertEqual([row.is_mailing_address for row in person.addresses], [0, 1])

	def test_notification_address_mirrors_only_the_primary_email(self):
		person = self._person(
			"Notify",
			emails=[{"email_address": "a@example.com"}, {"email_address": "b@example.com", "is_primary": 1}],
		)
		self.assertEqual([row.notification_address for row in person.emails], [None, "b@example.com"])


class TestDefaultContactTypes(FrappeTestCase):
	def test_seeding_is_idempotent(self):
		create_default_contact_types()
		before = frappe.db.count("Email Type"), frappe.db.count("Phone Type"), frappe.db.count("Address Type")
		create_default_contact_types()
		self.assertEqual(
			(frappe.db.count("Email Type"), frappe.db.count("Phone Type"), frappe.db.count("Address Type")),
			before,
		)
		for doctype, name in (("Email Type", "Home"), ("Phone Type", "Mobile"), ("Address Type", "Other")):
			self.assertTrue(frappe.db.exists(doctype, name))
