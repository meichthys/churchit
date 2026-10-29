# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""People imports, run end to end through a real Data Import as a church would run one."""

import csv
import io
import os
import warnings
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.importer import INSERT, UPDATE, UPSERT
from frappe.utils.xlsxutils import make_xlsx

from churchit.church_people.matching import POSSIBLE_DUPLICATE, Match
from churchit.tests.helpers import (
	RollbackEachTest,
	ensure_user,
	force_single_church,
	make_person,
	make_two_churches,
)

FILES = os.path.join(os.path.dirname(__file__), "test_files")
PEOPLE_IMPORT = "People Import"


def read_fixture(name: str) -> list[list[str]]:
	with open(os.path.join(FILES, name), newline="") as handle:
		return list(csv.reader(handle))


def edit(rows: list[list], first_name: str, **cells) -> list[list]:
	"""*rows* with the cells of *first_name*'s row changed, by column header."""
	header = rows[0]
	changed = [list(row) for row in rows]
	for row in changed[1:]:
		if first_name in row:
			for column, value in cells.items():
				row[header.index(column)] = value
	return changed


def column(rows: list[list], header: str) -> list:
	return [row[rows[0].index(header)] for row in rows[1:]]


def count_imported(doctype: str, system: str, ids: list) -> int:
	"""How many *doctype* records were imported from *system* under *ids*, whatever else the site holds."""
	return frappe.db.count(doctype, {"legacy_system": system, "legacy_id": ("in", ids)})


def get_person(first_name: str, **filters) -> frappe._dict:
	return frappe.get_all(
		"Person", filters={"first_name": first_name, **filters}, fields=["*"], order_by="creation desc"
	)[0]


class ImportCase(RollbackEachTest):
	"""Imports a file through Data Import inside the test's transaction. No one is a possible duplicate."""

	def setUp(self):
		super().setUp()
		matcher = patch("churchit.church_people.matching.find_matches", return_value=[])
		self.find_matches = matcher.start()
		self.addCleanup(matcher.stop)

	def run_import(self, doctype: str, rows: list[list], import_type: str = INSERT, xlsx: bool = False):
		return self.start(self.new_import(doctype, rows, import_type, xlsx))

	def new_import(self, doctype: str, rows: list[list], import_type: str = INSERT, xlsx: bool = False):
		return frappe.get_doc(
			{
				"doctype": "Data Import",
				"reference_doctype": doctype,
				"import_type": import_type,
				"import_file": self.make_file(rows, xlsx).file_url,
			}
		).insert()

	def start(self, data_import):
		# The importer commits after each row; keep its writes in the test's transaction instead.
		frappe.db._disable_transaction_control += 1
		try:
			with warnings.catch_warnings():
				warnings.simplefilter("ignore")
				data_import.start_import()
		finally:
			frappe.db._disable_transaction_control -= 1
		return data_import.reload()

	def preview_warnings(self, doctype: str, rows: list[list], import_type: str = INSERT) -> list[dict]:
		return self.new_import(doctype, rows, import_type).get_preview_from_template().warnings

	def make_file(self, rows: list[list], xlsx: bool):
		if xlsx:
			content, extension = make_xlsx(rows, "People").getvalue(), "xlsx"
		else:
			text = io.StringIO()
			csv.writer(text).writerows(rows)
			content, extension = text.getvalue(), "csv"
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"_test_import_{frappe.generate_hash(length=8)}.{extension}",
				"content": content,
				"is_private": 1,
			}
		).insert(ignore_permissions=True)
		# The rollback drops the File record but not the file on disk.
		self.addCleanup(remove_file, file.get_full_path())
		return file

	def assertImported(self, data_import, status="Success"):
		messages = frappe.get_all(
			"Data Import Log", filters={"data_import": data_import.name, "success": 0}, pluck="exception"
		)
		self.assertEqual(data_import.status, status, data_import.template_warnings or messages)

	def assertBlocked(self, data_import, message):
		self.assertEqual(data_import.status, "Pending")
		self.assertIn(message, data_import.template_warnings)


def remove_file(path: str):
	if os.path.exists(path):
		os.remove(path)


class TestPeopleImport(ImportCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		cls.rows = read_fixture("people.csv")

	def test_a_household_arriving_in_any_order_becomes_one_family(self):
		self.assertImported(self.run_import(PEOPLE_IMPORT, self.rows))

		alder, willow, bramble = (get_person(name) for name in ("Alder", "Willow", "Bramble"))
		family = frappe.get_doc("Family", alder.family)
		self.assertEqual({willow.family, bramble.family}, {family.name})
		self.assertEqual(
			(family.family_name, family.legacy_id, family.primary_contact),
			("Fernwood - Alder", "H-1", alder.name),
		)
		roles = {row.member: row.household_role for row in family.members}
		self.assertEqual(roles, {alder.name: "Adult", willow.name: "Adult", bramble.name: "Child"})
		self.assertEqual(
			(alder.source, alder.legacy_system, alder.legacy_id), ("Import", "Spreadsheet", "S-1")
		)
		self.assertEqual(
			(str(alder.birth_date), alder.membership, alder.marital_status),
			("1979-01-15", "Member", "Married"),
		)

	def test_a_household_shares_its_address_and_home_phone(self):
		self.run_import(PEOPLE_IMPORT, self.rows)

		alder, bramble, quill = (
			frappe.get_doc("Person", get_person(name).name) for name in ("Alder", "Bramble", "Quill")
		)
		family = frappe.get_doc("Family", alder.family)
		self.assertEqual(len(family.addresses), 1)
		self.assertEqual(
			frappe.db.get_value("Address", family.addresses[0].address, "address_line1"), "7 Juniper Way"
		)
		self.assertEqual((alder.addresses, bramble.addresses), ([], []))
		self.assertEqual(frappe.db.get_value("Address", quill.addresses[0].address, "city"), "Springfield")
		phones = {row.phone_type: row for row in alder.phones}
		self.assertEqual(phones["Mobile"].phone_number, "(555) 010-1001")
		self.assertEqual(phones["Home"].shared_from, bramble.name)
		self.assertEqual([row.email_address for row in alder.emails], ["alder.fernwood@example.com"])

	def test_each_new_person_and_family_names_its_data_import_in_its_history(self):
		data_import = self.run_import(PEOPLE_IMPORT, self.rows)

		alder = get_person("Alder")
		for doctype, name in (("Person", alder.name), ("Family", alder.family)):
			history = frappe.get_all(
				"Version", filters={"ref_doctype": doctype, "docname": name}, pluck="data"
			)
			self.assertTrue(any(data_import.name in data for data in history), f"{doctype} {name}")

	def test_importing_again_updates_the_people_instead_of_adding_them(self):
		self.run_import(PEOPLE_IMPORT, self.rows)
		rows = edit(self.rows, "Alder", **{"Mobile Phone": "(555) 010-9999", "Status": "Inactive"})

		data_import = self.run_import(PEOPLE_IMPORT, rows, UPSERT)

		self.assertImported(data_import)
		self.assertEqual(count_imported("Person", "Spreadsheet", column(self.rows, "Person ID")), 4)
		self.assertEqual(count_imported("Family", "Spreadsheet", ["H-1"]), 1)
		alder = frappe.get_doc("Person", get_person("Alder").name)
		self.assertEqual(alder.membership_status, "Inactive")
		self.assertIn("(555) 010-9999", [row.phone_number for row in alder.phones])
		actions = frappe.get_all(
			"Data Import Log", filters={"data_import": data_import.name}, pluck="import_action"
		)
		self.assertEqual(set(actions), {"Update"})

	def test_insert_new_records_refuses_people_imported_before(self):
		self.run_import(PEOPLE_IMPORT, self.rows)

		self.assertBlocked(self.run_import(PEOPLE_IMPORT, self.rows), "Already imported as")
		self.assertEqual(count_imported("Person", "Spreadsheet", column(self.rows, "Person ID")), 4)

	def test_update_existing_records_refuses_people_never_imported(self):
		self.assertBlocked(self.run_import(PEOPLE_IMPORT, self.rows, UPDATE), "no one to update")

	def test_a_row_with_no_first_name_blocks_the_import(self):
		rows = edit(self.rows, "Quill", **{"First Name": ""})

		self.assertBlocked(self.run_import(PEOPLE_IMPORT, rows), "no first name")
		self.assertEqual(count_imported("Person", "Spreadsheet", column(self.rows, "Person ID")), 0)

	def test_the_same_person_twice_in_one_file_blocks_the_import(self):
		self.assertBlocked(self.run_import(PEOPLE_IMPORT, [*self.rows, self.rows[2]]), "also on row 3")

	def test_an_invalid_email_is_left_out_with_a_note(self):
		rows = edit(self.rows, "Quill", **{"Home Email": "quill at example"})

		notes = [w["message"] for w in self.preview_warnings(PEOPLE_IMPORT, rows) if w.get("type") == "info"]
		self.assertIn("quill at example is not a valid email address. It is left out.", notes)
		self.assertImported(self.run_import(PEOPLE_IMPORT, rows))
		self.assertEqual(frappe.get_doc("Person", get_person("Quill").name).emails, [])

	def test_an_unknown_membership_waits_for_a_value_mapping(self):
		rows = edit(self.rows, "Quill", Membership="Friend of the Church")
		data_import = self.new_import(PEOPLE_IMPORT, rows)
		self.assertBlocked(self.start(data_import), "Friend of the Church")

		mapping = next(
			row for row in data_import.value_mappings if row.source_value == "Friend of the Church"
		)
		mapping.target_value = "Visitor"
		data_import.save()

		self.assertImported(self.start(data_import))
		self.assertEqual(get_person("Quill").membership, "Visitor")

	def test_imported_from_keeps_two_systems_apart(self):
		self.run_import(PEOPLE_IMPORT, self.rows)
		rows = [["Imported From", *self.rows[0]], ["Breeze", *self.rows[4]]]

		self.assertImported(self.run_import(PEOPLE_IMPORT, rows))
		self.assertEqual(get_person("Quill", legacy_system="Breeze").legacy_id, "S-4")
		self.assertEqual(frappe.db.count("Person", {"first_name": "Quill", "last_name": "Ashby"}), 2)

	def test_a_new_person_opens_a_possible_duplicate_for_each_match(self):
		existing = make_person("Quilla", "Ashby").name
		self.find_matches.return_value = [Match(existing, 92, ("same last name",))]

		self.assertImported(self.run_import(PEOPLE_IMPORT, self.rows[:1] + self.rows[4:]))

		quill = get_person("Quill")
		candidate = self.find_matches.call_args.args[0]
		self.assertEqual(
			(candidate["first_name"], candidate["emails"]), ("Quill", ["quill.ashby@example.com"])
		)
		self.assertEqual(self.find_matches.call_args.kwargs, {"church": quill.church, "exclude": quill.name})
		pair = frappe.get_all(
			POSSIBLE_DUPLICATE,
			filters={"person": existing},
			fields=["person", "other_person", "score", "reasons"],
		)
		self.assertEqual(
			pair, [{"person": existing, "other_person": quill.name, "score": 92, "reasons": "same last name"}]
		)

	def test_an_update_opens_no_possible_duplicate(self):
		self.run_import(PEOPLE_IMPORT, self.rows)
		self.find_matches.reset_mock()

		self.run_import(PEOPLE_IMPORT, self.rows, UPSERT)

		self.find_matches.assert_not_called()


class TestImportAtABranch(ImportCase):
	"""Imported people belong to the importer's church, and an import updates only that church's people."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user(
			"_test_import_manager_a@example.com", "ImportA", roles=("Church Manager",)
		)
		make_person("ImportA", "Manager", church=cls.branch_a, user=cls.manager_a)
		cls.rows = read_fixture("people.csv")

	def test_imported_people_and_families_land_in_the_importers_church(self):
		frappe.set_user(self.manager_a)

		self.assertImported(self.run_import(PEOPLE_IMPORT, self.rows))

		frappe.set_user("Administrator")
		alder = get_person("Alder")
		self.assertEqual(alder.church, self.branch_a)
		self.assertEqual(frappe.db.get_value("Family", alder.family, "church"), self.branch_a)

	def test_another_churchs_person_with_the_same_id_is_left_alone(self):
		theirs = make_person(
			"Quill", "Ashby", church=self.branch_b, legacy_system="Spreadsheet", legacy_id="S-4"
		)
		frappe.set_user(self.manager_a)

		self.assertImported(self.run_import(PEOPLE_IMPORT, self.rows[:1] + self.rows[4:], UPSERT))

		frappe.set_user("Administrator")
		self.assertEqual(get_person("Quill", church=self.branch_a).legacy_id, "S-4")
		self.assertFalse(frappe.get_doc("Person", theirs.name).emails)


class TestEnvelopeNumberImport(ImportCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()
		rows = read_fixture("people.csv")
		cls.rows = [[*rows[0], "Envelope Number"], *([*row, ""] for row in rows[1:])]

	def test_a_row_with_an_envelope_number_fills_the_field(self):
		rows = edit(self.rows, "Alder", **{"Envelope Number": "4021"})

		self.assertImported(self.run_import(PEOPLE_IMPORT, rows))

		self.assertEqual(get_person("Alder").envelope_number, "4021")
		self.assertIsNone(get_person("Bramble").envelope_number)
