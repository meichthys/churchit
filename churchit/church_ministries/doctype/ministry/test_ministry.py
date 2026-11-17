# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
import frappe.client
from frappe.desk.query_report import run
from frappe.exceptions import ValidationError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure_user, make_function


class TestMinistry(FrappeTestCase):
	def _make_ministry(self, name, **values):
		return frappe.get_doc({"doctype": "Ministry", "ministry_name": name, **values}).insert(
			ignore_permissions=True
		)

	def test_end_date_cannot_precede_start_date(self):
		with self.assertRaises(ValidationError):
			self._make_ministry("_Test Backwards", start_date="2030-02-01", end_date="2030-01-01")

	def test_recurring_functions_lists_repeating_templates_only(self):
		ministry = self._make_ministry("_Test Recurring Ministry")
		template = make_function(
			"_Test Weekly Template",
			associated_ministry=ministry.name,
			auto_repeat=1,
			repeat_frequency="Weekly",
			repeat_day_of_week="Sunday",
		)
		make_function("_Test One-Off", associated_ministry=ministry.name)

		ministry.reload()
		ministry.run_method("onload")

		rows = {row.function: row.repeat_frequency for row in ministry.recurring_functions}
		self.assertEqual(rows, {template.name: "Weekly"})

	def test_recurring_functions_refreshed_on_save(self):
		ministry = self._make_ministry("_Test Refreshed Ministry")
		make_function(
			"_Test Daily Template",
			associated_ministry=ministry.name,
			auto_repeat=1,
			repeat_frequency="Daily",
		)
		ministry.reload()
		ministry.save(ignore_permissions=True)
		self.assertEqual(len(ministry.recurring_functions), 1)

	def test_a_second_ministry_with_the_same_name_is_refused_in_plain_words(self):
		self._make_ministry("_Test Twin Ministry")
		with self.assertRaisesRegex(ValidationError, "There is already a ministry called"):
			self._make_ministry("_Test Twin Ministry")


class TestMinistryExpenses(FrappeTestCase):
	"""Total Expenses is a money figure: only the roles that read Expense see it."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.check_in = ensure_user(
			"_test_ministry_check_in@example.com", "MinistryCheckIn", ["Church Check-In"]
		)
		cls.staff = ensure_user("_test_ministry_staff@example.com", "MinistryStaff", ["Church Staff"])
		cls.manager = ensure_user("_test_ministry_manager@example.com", "MinistryManager", ["Church Manager"])
		cls.treasurer = ensure_user(
			"_test_ministry_treasurer@example.com", "MinistryTreasurer", ["Church Staff", "Church Finance"]
		)
		name = frappe.db.exists("Ministry", {"ministry_name": "_Test Costly Ministry"})
		cls.ministry = name or (
			frappe.get_doc({"doctype": "Ministry", "ministry_name": "_Test Costly Ministry"})
			.insert(ignore_permissions=True)
			.name
		)
		frappe.db.set_value("Ministry", cls.ministry, "total_expenses", 1234)

	def tearDown(self):
		frappe.set_user("Administrator")

	def read_as(self, user):
		"""The ministry as *user* receives it from the desk."""
		frappe.set_user(user)
		return frappe.client.get("Ministry", self.ministry)

	def test_only_the_roles_that_read_expenses_see_the_total(self):
		for user, sees in (
			(self.check_in, False),
			(self.staff, False),
			(self.manager, True),
			(self.treasurer, True),
		):
			with self.subTest(user):
				self.assertEqual(self.read_as(user).get("total_expenses") == 1234, sees)

	def test_a_check_in_volunteer_opens_the_ministries_report_without_expenses(self):
		frappe.set_user(self.check_in)

		result = run("Ministries", filters={})

		names = [row.get("name") for row in result["result"] if isinstance(row, dict)]
		self.assertIn(self.ministry, names)
		fieldnames = {column.get("fieldname") for column in result["columns"] if isinstance(column, dict)}
		self.assertNotIn("total_expenses", fieldnames)
		self.assertTrue(all("total_expenses" not in row for row in result["result"] if isinstance(row, dict)))
