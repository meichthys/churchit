# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A Planning Center export, a Rock RMS report and a Breeze export, as each system writes them, imported end to end."""

import frappe
from frappe.core.doctype.data_import.importer import UPSERT
from frappe.utils import getdate

from churchit.church_people.imports.test_imports import (
	ImportCase,
	column,
	count_imported,
	edit,
	get_person,
	read_fixture,
)
from churchit.tests.helpers import ensure, force_single_church

PLANNING_CENTER_IMPORT = "Planning Center Import"
ROCK_RMS_IMPORT = "Rock RMS Import"
BREEZE_IMPORT = "Breeze Import"
# Rock's Connection and Record Status values a church maps to its own once, on the Data Import
ROCK_MAPPINGS = {"Attendee": "Regular Attender", "Prospect": "Visitor", "Pending": "Active"}


def address_lines(doc) -> list[str]:
	return [frappe.db.get_value("Address", row.address, "address_line1") for row in doc.addresses]


class SourceCase(ImportCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		for salutation in ("Mr.", "Mrs."):
			ensure("Salutation", {"salutation": salutation})
		# A blank address country is the site's, which a test site may not have set.
		cls.addClassCleanup(frappe.db.set_default, "country", frappe.db.get_default("country"))
		frappe.db.set_default("country", "United States")

	def assertColumnsMapped(self, doctype, rows):
		"""Every column the DocType has a field for maps by itself, and every other one is only noted."""
		preview = self.new_import(doctype, rows).get_preview_from_template()
		fields = {df.label for df in frappe.get_meta(doctype).fields}
		mapped = {col.header_title for col in preview.columns if col.df}
		self.assertEqual(mapped, fields & set(rows[0]))
		unknown = [w for w in preview.warnings if w.get("code") == "unknown_column"]
		self.assertEqual(len(unknown), len(set(rows[0]) - fields))
		self.assertTrue(all(w["type"] == "info" for w in unknown))

	def get_household(self, first_name):
		person = get_person(first_name)
		family = frappe.get_doc("Family", person.family)
		people = {
			row.member: frappe.db.get_value("Person", row.member, "first_name") for row in family.members
		}
		roles = {people[row.member]: row.household_role for row in family.members}
		return family, roles, people.get(family.primary_contact)


class TestPlanningCenterImport(SourceCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.rows = read_fixture("planning_center.csv")

	def test_an_export_maps_without_column_mapping(self):
		self.assertColumnsMapped(PLANNING_CENTER_IMPORT, self.rows)

	def test_a_household_takes_its_primary_contact_and_children_from_the_export(self):
		self.assertImported(self.run_import(PLANNING_CENTER_IMPORT, self.rows))

		family, roles, primary_contact = self.get_household("Juniper")
		self.assertEqual(
			(family.family_name, family.legacy_system, family.legacy_id),
			("Larkspur Household", "Planning Center", "9001"),
		)
		self.assertEqual(roles, {"Juniper": "Child", "Rosalind": "Adult", "Everett": "Adult"})
		self.assertEqual(primary_contact, "Everett")
		self.assertEqual(len(family.addresses), 1)

	def test_the_columns_become_the_persons_details(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)

		everett = frappe.get_doc("Person", get_person("Everett").name)
		self.assertEqual(
			(everett.prefix, everett.middle_name, everett.suffix, everett.gender, str(everett.anniversary)),
			("Mr.", "James", "Jr.", "Male", "2008-06-21"),
		)
		self.assertEqual(
			(everett.membership, everett.membership_status, everett.legacy_id), ("Member", "Active", "41001")
		)
		self.assertEqual(
			{(row.email_type, row.email_address) for row in everett.emails},
			{("Home", "everett.larkspur@example.com"), ("Work", "everett@work.example.com")},
		)
		self.assertEqual({row.phone_type for row in everett.phones}, {"Mobile", "Home", "Work"})
		self.assertEqual(get_person("Rosalind").nickname, "Ros")
		self.assertEqual(get_person("Juniper").medical_notes, "Peanut allergy")

	def test_a_member_living_elsewhere_keeps_their_own_address_whatever_the_row_order(self):
		rows = edit(self.rows, "Juniper", **{"Home Address Street Line 1": "1 College Hall"})

		self.run_import(PLANNING_CENTER_IMPORT, rows)

		juniper = frappe.get_doc("Person", get_person("Juniper").name)
		family = frappe.get_doc("Family", juniper.family)
		self.assertEqual(address_lines(family), ["22 Thistle Road"])
		self.assertEqual(address_lines(juniper), ["1 College Hall"])

	def test_a_household_that_moved_takes_its_new_address(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)
		moved = self.rows
		for first_name in ("Juniper", "Rosalind", "Everett"):
			moved = edit(moved, first_name, **{"Home Address Street Line 1": "8 Bramble Way"})

		self.assertImported(self.run_import(PLANNING_CENTER_IMPORT, moved, UPSERT))

		family = frappe.get_doc("Family", get_person("Everett").family)
		current = [row.address for row in family.addresses if row.is_primary and row.is_mailing_address]
		self.assertEqual(address_lines(family), ["22 Thistle Road", "8 Bramble Way"])
		self.assertEqual(frappe.db.get_value("Address", current[0], "address_line1"), "8 Bramble Way")
		for first_name in ("Juniper", "Rosalind", "Everett"):
			self.assertEqual(address_lines(frappe.get_doc("Person", get_person(first_name).name)), [])

	def test_several_emails_in_one_cell_become_several_rows(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)

		marigold = frappe.get_doc("Person", get_person("Marigold").name)
		self.assertEqual(
			[row.email_address for row in marigold.emails], ["marigold.fenn@example.com", "mfenn@example.com"]
		)

	def test_a_birth_year_of_1885_is_an_unknown_year(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)

		marigold = get_person("Marigold")
		self.assertEqual((marigold.birth_date, marigold.birth_month, marigold.birth_day), (None, 7, 4))

	def test_a_deceased_inactive_reason_records_the_death(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)

		basil = get_person("Basil")
		self.assertEqual(
			(basil.is_deceased, basil.membership_status, basil.inactive_reason), (1, "Inactive", "Deceased")
		)

	def test_a_later_export_updates_the_same_people(self):
		self.run_import(PLANNING_CENTER_IMPORT, self.rows)
		rows = edit(self.rows, "Rosalind", **{"Home Email": "rosalind@example.com", "Membership": "Member"})

		self.assertImported(self.run_import(PLANNING_CENTER_IMPORT, rows, UPSERT))

		self.assertEqual(count_imported("Person", "Planning Center", column(self.rows, "Person ID")), 5)
		rosalind = frappe.get_doc("Person", get_person("Rosalind").name)
		self.assertEqual(
			[row.email_address for row in rosalind.emails],
			["ros.larkspur@example.com", "rosalind@example.com"],
		)


class TestRockRMSImport(SourceCase):
	"""A report exported to Excel: dates arrive as Excel dates, and Rock's own statuses need mapping once."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		rows = read_fixture("rock_rms.csv")
		dates = [rows[0].index("Birthdate"), rows[0].index("Anniversary Date")]
		cls.rows = [rows[0]] + [
			[getdate(cell) if index in dates and cell else cell for index, cell in enumerate(row)]
			for row in rows[1:]
		]

	def run_rock_import(self, import_type=None):
		data_import = self.new_import(
			ROCK_RMS_IMPORT, self.rows, import_type or "Insert New Records", xlsx=True
		)
		for mapping in data_import.value_mappings:
			mapping.target_value = ROCK_MAPPINGS[mapping.source_value]
		data_import.save()
		return self.start(data_import)

	def test_a_report_maps_without_column_mapping(self):
		self.assertColumnsMapped(ROCK_RMS_IMPORT, self.rows)

	def test_rock_statuses_wait_for_a_value_mapping(self):
		data_import = self.new_import(ROCK_RMS_IMPORT, self.rows, xlsx=True)

		self.assertEqual({row.source_value for row in data_import.value_mappings}, set(ROCK_MAPPINGS))
		self.assertBlocked(self.start(data_import), "Attendee")

	def test_the_first_adult_of_a_family_becomes_its_primary_contact(self):
		self.assertImported(self.run_rock_import())

		family, roles, primary_contact = self.get_household("Oakley")
		self.assertEqual(
			(family.family_name, family.legacy_system, family.legacy_id),
			("Wrenfield Family", "Rock RMS", "77"),
		)
		self.assertEqual(roles, {"Oakley": "Child", "Hazel": "Adult", "Thaddeus": "Adult"})
		self.assertEqual(primary_contact, "Hazel")

	def test_the_columns_become_the_persons_details(self):
		self.run_rock_import()

		tad = frappe.get_doc("Person", get_person("Thaddeus").name)
		self.assertEqual(
			(tad.nickname, tad.prefix, str(tad.birth_date), tad.legacy_id),
			("Tad", "Mr.", "1986-01-30", "1201"),
		)
		self.assertEqual(get_person("Oakley").membership, "Regular Attender")
		self.assertEqual(get_person("Imogen").membership_status, "Active")
		self.assertEqual(get_person("Clement").is_deceased, 1)
		address = frappe.get_doc("Family", tad.family).addresses[0].address
		self.assertEqual(
			frappe.db.get_value("Address", address, ["city", "country"]), ("Lincoln", "United States")
		)

	def test_a_later_report_updates_the_same_people(self):
		self.run_rock_import()

		self.assertImported(self.run_rock_import(UPSERT))

		self.assertEqual(count_imported("Person", "Rock RMS", column(self.rows, "Id")), 5)
		self.assertEqual(count_imported("Family", "Rock RMS", column(self.rows, "Family Id")), 3)


class TestBreezeImport(SourceCase):
	"""Two Hartwell families: Samuel, Leah and their son Micah, and Owen with his daughter Ivy and his mother Hazel."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for membership in ("Member", "Visitor"):
			ensure("Membership Type", {"type": membership})
		cls.rows = read_fixture("breeze.csv")

	def test_an_export_maps_without_column_mapping(self):
		self.assertColumnsMapped(BREEZE_IMPORT, self.rows)

	def test_each_family_takes_its_head_of_household_as_primary_contact_and_its_children(self):
		self.assertImported(self.run_import(BREEZE_IMPORT, self.rows))

		family, roles, primary_contact = self.get_household("Micah")
		self.assertEqual(
			(family.family_name, family.legacy_system, family.legacy_id),
			("Hartwell - Samuel", "Breeze", "8801"),
		)
		self.assertEqual(roles, {"Micah": "Child", "Samuel": "Adult", "Leah": "Adult"})
		self.assertEqual(primary_contact, "Samuel")
		self.assertEqual(address_lines(family), ["14 Juniper Lane"])

	def test_families_with_one_surname_and_two_family_ids_stay_two_families(self):
		self.run_import(BREEZE_IMPORT, self.rows)

		family, roles, primary_contact = self.get_household("Ivy")
		self.assertNotEqual(family.name, get_person("Samuel").family)
		self.assertEqual((family.family_name, family.legacy_id), ("Hartwell - Owen", "8802"))
		self.assertEqual(primary_contact, "Owen")
		# Unassigned leaves the role to the family's rule: an adult with no relationship is an Other Adult.
		self.assertEqual(roles, {"Owen": "Adult", "Ivy": "Child", "Hazel": "Other Adult"})

	def test_the_columns_become_the_persons_details(self):
		self.run_import(BREEZE_IMPORT, self.rows)

		samuel = frappe.get_doc("Person", get_person("Samuel").name)
		self.assertEqual(
			(samuel.nickname, samuel.middle_name, samuel.gender, str(samuel.birth_date), samuel.legacy_id),
			("Sam", "Lee", "Male", "1981-11-02", "31001"),
		)
		self.assertEqual((samuel.membership, samuel.marital_status), ("Member", "Married"))
		self.assertEqual([row.email_address for row in samuel.emails], ["sam.hartwell@example.com"])
		self.assertEqual({row.phone_type for row in samuel.phones}, {"Mobile", "Home", "Work"})
		self.assertEqual(get_person("Owen").membership, "Visitor")

	def test_a_second_import_of_the_same_file_adds_no_one(self):
		self.run_import(BREEZE_IMPORT, self.rows)

		self.assertImported(self.run_import(BREEZE_IMPORT, self.rows, UPSERT))

		self.assertEqual(count_imported("Person", "Breeze", column(self.rows, "Breeze ID")), 6)
		self.assertEqual(count_imported("Family", "Breeze", column(self.rows, "Family")), 2)
