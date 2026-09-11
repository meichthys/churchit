# Copyright (c) 2025, meichthys and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from churchit.church_missions.doctype.missionary.missionary import (
	create_missionary_expenses,
	get_map_markers,
	get_public_map_markers,
)

TEST_POINT_GEOJSON = (
	'{"type":"FeatureCollection","features":[{"type":"Feature",'
	'"geometry":{"type":"Point","coordinates":[-77.03, 38.9]},"properties":{}}]}'
)

TEST_FUND = "Test Missions Fund"
TEST_EXPENSE_TYPE = "Test Missionary Support"
TEST_PERSON_NAME = "Test Missionary Person"
TEST_MISSIONARY_TITLE = "Test Missionary"


def _ensure(doctype, filters, values):
	name = frappe.db.exists(doctype, filters)
	if name:
		return name
	return frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True).name


class TestMissionary(FrappeTestCase):
	def setUp(self):
		# Tree-doctype (Expense Type) inserts commit, so rollback can't fully isolate
		# these tests — clear any leftover missionary/expenses up front instead.
		for missionary in frappe.get_all(
			"Missionary", filters={"title": ["like", f"{TEST_MISSIONARY_TITLE}%"]}, pluck="name"
		):
			frappe.db.delete("Expense", {"missionary": missionary})
			frappe.delete_doc("Missionary", missionary, force=True, ignore_permissions=True)

		fund = _ensure("Fund", {"fund": TEST_FUND}, {"fund": TEST_FUND})
		self.expense_type = _ensure(
			"Expense Type", {"type": TEST_EXPENSE_TYPE}, {"type": TEST_EXPENSE_TYPE, "fund": fund}
		)
		self.person = _ensure(
			"Person", {"first_name": TEST_PERSON_NAME}, {"first_name": TEST_PERSON_NAME}
		)

	def tearDown(self):
		# A commit() elsewhere in the same test run ends the whole session's rollback
		# scope, which would otherwise leave this test's Missionary/Expense records
		# committed for real. Delete and commit explicitly rather than rely on it.
		for missionary in frappe.get_all(
			"Missionary", filters={"title": ["like", f"{TEST_MISSIONARY_TITLE}%"]}, pluck="name"
		):
			frappe.db.delete("Expense", {"missionary": missionary})
			frappe.delete_doc("Missionary", missionary, force=True, ignore_permissions=True)
		frappe.db.commit()

	def _make_missionary(self, **overrides):
		data = {
			"doctype": "Missionary",
			"title": TEST_MISSIONARY_TITLE,
			"person": self.person,
			"support_amount": 100,
			"support_frequency": "Monthly",
			"support_start_date": add_days(today(), -70),
			"auto_create_expenses": 1,
			"expense_type": self.expense_type,
		}
		data.update(overrides)
		return frappe.get_doc(data).insert(ignore_permissions=True)

	def test_auto_create_backfills_due_draft_expenses(self):
		missionary = self._make_missionary()
		create_missionary_expenses()

		expenses = frappe.get_all(
			"Expense",
			filters={"missionary": missionary.name},
			fields=["amount", "docstatus", "type"],
		)
		# Start 70 days ago, monthly -> 3 periods due on/before today.
		self.assertEqual(len(expenses), 3)
		for expense in expenses:
			self.assertEqual(expense.amount, 100)
			self.assertEqual(expense.docstatus, 0)  # left as draft for review
			self.assertEqual(expense.type, missionary.expense_type)

	def test_auto_create_is_idempotent(self):
		missionary = self._make_missionary()
		create_missionary_expenses()
		create_missionary_expenses()
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 3)

	def test_auto_create_stops_after_support_end_date(self):
		missionary = self._make_missionary(support_end_date=add_days(today(), -40))
		create_missionary_expenses()
		# Only periods on/before the end date (start, +1 month) should exist.
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 2)

	def test_disabled_missionary_creates_nothing(self):
		missionary = self._make_missionary(auto_create_expenses=0)
		create_missionary_expenses()
		self.assertEqual(frappe.db.count("Expense", {"missionary": missionary.name}), 0)

	def test_requires_positive_amount_when_enabled(self):
		from frappe.exceptions import ValidationError

		with self.assertRaises(ValidationError):
			self._make_missionary(support_amount=0)

	def test_map_markers_only_include_located_missionaries(self):
		located = self._make_missionary(
			auto_create_expenses=0, geolocation=TEST_POINT_GEOJSON, country="United States"
		)
		self._make_missionary(auto_create_expenses=0, title=f"{TEST_MISSIONARY_TITLE} Unlocated")

		markers = [m for m in get_map_markers() if m["name"] == located.name]
		self.assertEqual(len(markers), 1)
		marker = markers[0]
		self.assertEqual(marker["title"], TEST_MISSIONARY_TITLE)
		self.assertEqual(marker["country"], "United States")
		self.assertAlmostEqual(marker["latitude"], 38.9)
		self.assertAlmostEqual(marker["longitude"], -77.03)

	def test_public_map_markers_exclude_unpublished_and_sensitive(self):
		hidden_count_before = get_public_map_markers()["hidden_count"]

		self._make_missionary(
			auto_create_expenses=0,
			title=f"{TEST_MISSIONARY_TITLE} Published",
			geolocation=TEST_POINT_GEOJSON,
			publish=1,
		)
		self._make_missionary(
			auto_create_expenses=0,
			title=f"{TEST_MISSIONARY_TITLE} Sensitive",
			geolocation=TEST_POINT_GEOJSON,
			publish=1,
			sensitive=1,
		)
		self._make_missionary(
			auto_create_expenses=0,
			title=f"{TEST_MISSIONARY_TITLE} Unpublished",
			geolocation=TEST_POINT_GEOJSON,
			publish=0,
		)

		result = get_public_map_markers()
		titles = {m["title"] for m in result["markers"]}
		self.assertIn(f"{TEST_MISSIONARY_TITLE} Published", titles)
		self.assertNotIn(f"{TEST_MISSIONARY_TITLE} Sensitive", titles)
		self.assertNotIn(f"{TEST_MISSIONARY_TITLE} Unpublished", titles)
		self.assertEqual(result["hidden_count"], hidden_count_before + 1)

		published_marker = next(
			m for m in result["markers"] if m["title"] == f"{TEST_MISSIONARY_TITLE} Published"
		)
		self.assertNotIn("name", published_marker)
