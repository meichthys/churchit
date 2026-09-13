# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.giving_statement.giving_statement import (
	generate_statements,
	get_statement_recipients,
	statement_header,
)
from churchit.tests.helpers import ensure, make_person

PERIOD = ("2029-01-01", "2029-12-31")


def make_collection(date, donations, submit=True):
	"""A Collection carrying one Donation row per (person, amount) pair."""
	fund = ensure("Fund", {"fund": "_Test Statement Fund"})
	payment_type = ensure("Payment Type", {"type": "_Test Statement Cash"}, {"type": "_Test Statement Cash"})
	collection = frappe.get_doc(
		{"doctype": "Collection", "date": date, "expected_total": sum(a for _p, a in donations)}
	)
	for person, amount in donations:
		collection.append(
			"donations",
			{"person": person, "amount": amount, "fund": fund, "payment_type": payment_type},
		)
	collection.insert(ignore_permissions=True)
	if submit:
		collection.submit()
	return collection


class TestGivingStatement(FrappeTestCase):
	def setUp(self):
		self.giver = make_person("_Test Statement", "Giver")

	def _statement(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Giving Statement",
				"person": self.giver.name,
				"from_date": PERIOD[0],
				"to_date": PERIOD[1],
				**values,
			}
		).insert(ignore_permissions=True)

	def test_lines_and_total_come_from_submitted_donations(self):
		make_collection("2029-03-01", [(self.giver.name, 100)])
		make_collection("2029-06-01", [(self.giver.name, 250)])

		statement = self._statement()

		self.assertEqual(len(statement.lines), 2)
		self.assertEqual(statement.total_amount, 350)

	def test_draft_collections_are_excluded(self):
		make_collection("2029-03-01", [(self.giver.name, 100)], submit=False)
		self.assertEqual(self._statement().total_amount, 0)

	def test_gifts_outside_the_period_are_excluded(self):
		make_collection("2028-12-31", [(self.giver.name, 500)])
		make_collection("2029-05-05", [(self.giver.name, 75)])

		statement = self._statement()

		self.assertEqual(len(statement.lines), 1)
		self.assertEqual(statement.total_amount, 75)

	def test_household_statement_covers_every_family_member(self):
		family = frappe.get_doc(
			{"doctype": "Family", "family_name": "_Test Statement Household"}
		).insert(ignore_permissions=True)
		self.giver.family = family.name
		self.giver.save(ignore_permissions=True)
		spouse = make_person("_Test Statement", "Spouse", family=family.name)

		make_collection("2029-04-01", [(self.giver.name, 60), (spouse.name, 40)])

		statement = self._statement(family=family.name)

		self.assertEqual(statement.total_amount, 100)
		self.assertCountEqual(
			[line.person for line in statement.lines], [self.giver.name, spouse.name]
		)

	def test_rebuilding_replaces_lines_rather_than_appending(self):
		make_collection("2029-03-01", [(self.giver.name, 100)])
		statement = self._statement()

		statement.save(ignore_permissions=True)

		self.assertEqual(len(statement.lines), 1)
		self.assertEqual(statement.total_amount, 100)

	def test_title_carries_the_name_and_year(self):
		statement = self._statement()
		self.assertEqual(statement.title, f"{self.giver.full_name} - 2029")

	def test_reversed_dates_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self._statement(from_date="2029-12-31", to_date="2029-01-01")


class TestStatementGeneration(FrappeTestCase):
	def setUp(self):
		frappe.db.set_single_value("Giving Settings", "statement_grouping", "Household")

	def test_household_grouping_issues_one_statement_per_family(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Gen Household"}).insert(
			ignore_permissions=True
		)
		head = make_person("_Test Gen", "Head", family=family.name, is_head_of_household=1)
		spouse = make_person("_Test Gen", "Spouse", family=family.name)
		make_collection("2029-02-02", [(head.name, 10), (spouse.name, 20)])

		recipients = get_statement_recipients(*PERIOD)
		ours = [r for r in recipients if r["family"] == family.name]

		self.assertEqual(len(ours), 1)
		self.assertEqual(ours[0]["person"], head.name, "addressed to the head of household")

	def test_person_grouping_issues_one_statement_each(self):
		frappe.db.set_single_value("Giving Settings", "statement_grouping", "Person")
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Gen Split"}).insert(
			ignore_permissions=True
		)
		one = make_person("_Test Split", "One", family=family.name)
		two = make_person("_Test Split", "Two", family=family.name)
		make_collection("2029-02-02", [(one.name, 10), (two.name, 20)])

		people = [r["person"] for r in get_statement_recipients(*PERIOD)]

		self.assertIn(one.name, people)
		self.assertIn(two.name, people)

	def test_generation_is_idempotent(self):
		giver = make_person("_Test Idempotent", "Giver")
		make_collection("2029-07-07", [(giver.name, 45)])

		first = generate_statements(*PERIOD)
		second = generate_statements(*PERIOD)

		self.assertGreaterEqual(first["created"], 1)
		self.assertEqual(second["created"], 0, "a second run rebuilds rather than duplicates")
		self.assertEqual(
			frappe.db.count("Giving Statement", {"person": giver.name, "from_date": PERIOD[0]}), 1
		)

	def test_people_without_gifts_get_no_statement(self):
		quiet = make_person("_Test Quiet", "Person")
		generate_statements(*PERIOD)
		self.assertFalse(frappe.db.exists("Giving Statement", {"person": quiet.name}))


class TestStatementHeader(FrappeTestCase):
	def test_header_prefers_the_legal_name_and_carries_the_acknowledgment(self):
		frappe.db.set_single_value("Giving Settings", "statement_acknowledgment", "_Test wording.")
		church = frappe.get_all("Church", order_by="lft asc", limit=1, pluck="name")[0]
		frappe.db.set_value("Church", church, {"legal_name": "_Test Legal Name", "tax_id": "12-3456789"})

		header = statement_header()

		self.assertEqual(header["name"], "_Test Legal Name")
		self.assertEqual(header["tax_id"], "12-3456789")
		self.assertEqual(header["acknowledgment"], "_Test wording.")
