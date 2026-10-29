# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.core.doctype.data_import.importer import UPSERT
from frappe.utils import get_datetime, today

from churchit.church_finances.doctype.online_donation.test_online_donation import log_charge, make_gift
from churchit.church_finances.imports import giving
from churchit.church_finances.imports.giving import GivingImportProvider
from churchit.church_people.imports.test_imports import ImportCase
from churchit.tests.helpers import ensure, ensure_user, force_single_church, make_person, make_two_churches

GIVING_IMPORT = "Giving Import"
HEADER = [
	"Gift ID",
	"Date",
	"Amount",
	"Fund",
	"Payment Type",
	"Check Number",
	"Imported From",
	"Person ID",
	"Email",
	"Batch",
	"Notes",
]


class GivingImportCase(ImportCase):
	def setUp(self):
		super().setUp()

		self.fund = ensure("Fund", {"fund": "_Test Import Fund"})
		self.payment_type = ensure("Payment Type", {"type": "_Test Import Check"})
		self.giver = make_person("_Test Import", "Giver", legacy_system="Spreadsheet", legacy_id="G-1")
		self.emailed = make_person(
			"_Test Import", "Emailed", emails=[{"email_address": "_test_import_giver@example.com"}]
		)

	def row(self, gift_id, date="2031-09-07", amount=25, **cells) -> list:
		values = {
			"Gift ID": gift_id,
			"Date": date,
			"Amount": amount,
			"Fund": self.fund,
			"Payment Type": self.payment_type,
			"Person ID": "G-1",
			"Batch": "_Test Batch",
			**cells,
		}
		return [values.get(column, "") for column in HEADER]

	def get_collections(self, batch="_Test Batch") -> list:
		return frappe.get_all(
			"Collection",
			filters={"import_batch": batch},
			fields=["name", "date", "expected_total", "total_amount", "docstatus", "church"],
			order_by="date asc",
		)

	def assertRowBlocked(self, rows: list[list], message: str):
		warnings = self.preview_warnings(GIVING_IMPORT, [HEADER, *rows])
		self.assertEqual([warning["row"] for warning in warnings], list(range(2, len(rows) + 2)), warnings)
		self.assertTrue(all(message in warning["message"] for warning in warnings), warnings)


class TestGivingImport(GivingImportCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		force_single_church()

	def test_rows_of_one_batch_and_date_make_one_draft_collection(self):
		rows = [
			self.row("ch_1", amount=25, **{"Check Number": "1001"}),
			self.row("ch_2", amount=15.5, **{"Person ID": "", "Email": "_TEST_import_giver@example.com"}),
			self.row("ch_3", date="2031-09-14", amount=40),
		]

		self.assertImported(self.run_import(GIVING_IMPORT, [HEADER, *rows]))

		first, second = self.get_collections()
		self.assertEqual(
			(first.date, first.expected_total, first.total_amount, first.docstatus),
			(get_datetime("2031-09-07"), 40.5, 40.5, 0),
		)
		self.assertEqual((second.date, second.expected_total), (get_datetime("2031-09-14"), 40))
		donations = {row.legacy_id: row for row in frappe.get_doc("Collection", first.name).donations}
		self.assertEqual(
			{gift_id: (row.person, row.amount, row.fund) for gift_id, row in donations.items()},
			{
				"ch_1": (self.giver.name, 25, self.fund),
				"ch_2": (self.emailed.name, 15.5, self.fund),
			},
		)
		self.assertEqual(donations["ch_1"].check_number, "1001")

	def test_a_date_with_a_time_goes_in_that_days_collection(self):
		rows = [self.row("ch_1", date="2031-09-07 00:00:01"), self.row("ch_2", date="2031-09-07 23:59:59")]

		self.assertImported(self.run_import(GIVING_IMPORT, [HEADER, *rows]))

		self.assertEqual([c.date for c in self.get_collections()], [get_datetime("2031-09-07")])

	def test_a_second_import_of_the_same_file_blocks_every_row(self):
		rows = [self.row("ch_1"), self.row("ch_2", date="2031-09-14")]
		self.run_import(GIVING_IMPORT, [HEADER, *rows])

		self.assertRowBlocked(rows, "already imported")
		self.assertBlocked(self.run_import(GIVING_IMPORT, [HEADER, *rows]), "already imported")
		self.assertEqual(len(self.get_collections()), 2)

	def test_a_gift_imported_after_the_preview_is_refused(self):
		self.run_import(GIVING_IMPORT, [HEADER, self.row("ch_1")])
		doc = {"gift_id": "ch_1", "date": "2031-09-07", "amount": 25, "fund": self.fund, "person_id": "G-1"}
		importer = SimpleNamespace(data_import=frappe._dict(name="_Test Data Import"))

		with (
			patch.object(giving, "get_imported_gift_ids", wraps=giving.get_imported_gift_ids) as read,
			self.assertRaisesRegex(frappe.ValidationError, "already imported"),
		):
			GivingImportProvider().import_row(importer, doc)
		read.assert_called_once_with({"ch_1"}, for_update=True)

	def test_a_gift_twice_in_one_file_blocks_the_second_row(self):
		warnings = self.preview_warnings(GIVING_IMPORT, [HEADER, self.row("ch_1"), self.row("ch_1")])

		self.assertEqual([(w["row"], w["message"]) for w in warnings], [(3, "This gift is also on row 2.")])

	def test_a_gift_on_a_cancelled_collection_imports_again(self):
		self.run_import(GIVING_IMPORT, [HEADER, self.row("ch_1")])
		collection = frappe.get_doc("Collection", self.get_collections()[0].name)
		collection.submit()
		collection.cancel()

		self.assertEqual(self.preview_warnings(GIVING_IMPORT, [HEADER, self.row("ch_1")]), [])

	def test_an_unknown_fund_or_payment_type_blocks_the_import(self):
		for column in ("Fund", "Payment Type"):
			with self.subTest(column):
				data_import = self.run_import(
					GIVING_IMPORT, [HEADER, self.row("ch_1", **{column: "_Test No Such Value"})]
				)

				self.assertBlocked(data_import, "_Test No Such Value")
				self.assertEqual(self.get_collections(), [])

	def test_a_non_cash_payment_type_blocks_the_row(self):
		goods = ensure(
			"Payment Type", {"type": "_Test Import Goods"}, {"type": "_Test Import Goods", "is_non_cash": 1}
		)

		self.assertRowBlocked(
			[self.row("ch_1", **{"Payment Type": goods})], "Non-cash gifts cannot be imported"
		)

	def test_a_row_with_no_giver_or_two_givers_is_blocked(self):
		shared = "_test_import_shared@example.com"
		spouse = make_person("_Test Import", "Spouse", emails=[{"email_address": shared}])
		make_person(
			"_Test Import",
			"Other",
			emails=[{"email_address": shared, "shared_from_type": "Person", "shared_from": spouse.name}],
		)

		self.assertRowBlocked(
			[self.row("ch_1", **{"Person ID": "G-404"}), self.row("ch_2", **{"Person ID": "", "Email": ""})],
			"No one has this Person ID or email",
		)
		self.assertRowBlocked(
			[self.row("ch_3", **{"Person ID": "", "Email": "_test_import_shared@example.com"})],
			"More than one person has this email",
		)

	def test_a_row_matching_a_paid_online_donation_is_blocked(self):
		gift = {"doctype": "Online Donation", "fund": self.fund, "currency": "USD", "status": "Paid"}
		frappe.get_doc(
			{**gift, "amount": 30, "fee_amount": 1.17, "email": "_test_import_giver@example.com"}
		).insert(ignore_permissions=True)
		frappe.get_doc({**gift, "amount": 12, "person": self.emailed.name}).insert(ignore_permissions=True)
		by_email = {"Person ID": "", "Email": "_test_import_giver@example.com"}

		self.assertRowBlocked(
			[
				self.row("ch_1", date=today(), amount=31.17, **by_email),
				self.row("ch_2", date=today(), amount=12, **by_email),
			],
			"An Online Donation that the gateway charged has the same amount, date and email",
		)
		self.assertEqual(
			self.preview_warnings(
				GIVING_IMPORT, [HEADER, self.row("ch_3", date=today(), amount=30, **by_email)]
			),
			[],
		)

	def test_a_row_matching_a_charged_gift_that_is_not_recorded_yet_is_blocked(self):
		email = {"email": "_test_import_giver@example.com"}
		log_charge(make_gift(self.fund, 20, status="Pending", **email))
		make_gift(self.fund, 21, status="Needs Review", **email)
		make_gift(self.fund, 22, status="Pending", **email)
		by_email = {"Person ID": "", "Email": email["email"]}

		self.assertRowBlocked(
			[
				self.row("ch_1", date=today(), amount=20, **by_email),
				self.row("ch_2", date=today(), amount=21, **by_email),
			],
			"An Online Donation that the gateway charged has the same amount, date and email",
		)
		self.assertEqual(
			self.preview_warnings(
				GIVING_IMPORT, [HEADER, self.row("ch_3", date=today(), amount=22, **by_email)]
			),
			[],
		)

	def test_amounts_are_rounded_so_the_collection_balances(self):
		rows = [self.row("ch_1", amount=10.004), self.row("ch_2", amount=10.004)]

		self.assertImported(self.run_import(GIVING_IMPORT, [HEADER, *rows]))

		collection = frappe.get_doc("Collection", self.get_collections()[0].name)
		self.assertEqual((collection.expected_total, collection.total_amount), (20, 20))
		collection.submit()

	def test_only_insert_new_records_is_offered(self):
		warnings = self.preview_warnings(GIVING_IMPORT, [HEADER, self.row("ch_1")], UPSERT)

		self.assertEqual(
			[w["message"] for w in warnings], ["A giving import only adds gifts. Choose Insert New Records."]
		)


class TestGivingImportAtABranch(GivingImportCase):
	"""An import adds gifts to Collections of the importer's church, and only to its own or shared funds."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user(
			"_test_giving_import_manager_a@example.com", "GivingA", roles=("Church Manager",)
		)
		make_person("GivingA", "Manager", church=cls.branch_a, user=cls.manager_a)

	def setUp(self):
		super().setUp()
		for person in (self.giver.name, self.emailed.name):
			frappe.db.set_value("Person", person, "church", self.branch_a)
		frappe.db.set_value("Fund", self.fund, "church", self.branch_a)

	def test_the_collection_takes_the_importers_church(self):
		frappe.set_user(self.manager_a)

		self.assertImported(self.run_import(GIVING_IMPORT, [HEADER, self.row("ch_1")]))

		frappe.set_user("Administrator")
		self.assertEqual([c.church for c in self.get_collections()], [self.branch_a])

	def test_a_fund_of_another_church_blocks_the_row(self):
		theirs = frappe.get_doc(
			{"doctype": "Fund", "fund": "_Test Import Their Fund", "church": self.branch_b}
		).insert(ignore_permissions=True)
		frappe.set_user(self.manager_a)

		self.assertRowBlocked([self.row("ch_1", Fund=theirs.name)], "belongs to another church")

	def test_another_churchs_giver_is_not_found(self):
		make_person(
			"_Test Import",
			"Theirs",
			church=self.branch_b,
			emails=[{"email_address": "_test_import_theirs@example.com"}],
		)
		frappe.set_user(self.manager_a)

		self.assertRowBlocked(
			[self.row("ch_1", **{"Person ID": "", "Email": "_test_import_theirs@example.com"})],
			"No one has this Person ID or email",
		)
