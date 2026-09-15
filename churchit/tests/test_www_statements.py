# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The member-facing /statements page: a giver sees their own statements and no one else's."""

import frappe
from frappe.exceptions import PermissionError
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure_user, make_person
from churchit.www.statements import get_context

PERIOD = ("2029-01-01", "2029-12-31")


class TestStatementsPage(FrappeTestCase):
	def setUp(self):
		frappe.local.form_dict = frappe._dict()
		self.email = ensure_user("_test_statement_member@example.com", "Statement")
		self.person = make_person("_Test Portal", "Giver", user=self.email)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.form_dict = frappe._dict()

	def _statement(self, person, **values):
		return frappe.get_doc(
			{
				"doctype": "Giving Statement",
				"person": person,
				"from_date": PERIOD[0],
				"to_date": PERIOD[1],
				**values,
			}
		).insert(ignore_permissions=True)

	def _context(self):
		context = frappe._dict()
		get_context(context)
		return context

	def test_guests_are_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			self._context()

	def test_member_sees_their_own_statement(self):
		statement = self._statement(self.person.name)
		frappe.set_user(self.email)

		names = [row.name for row in self._context().statements]

		self.assertIn(statement.name, names)

	def test_member_does_not_see_another_persons_statement(self):
		other = make_person("_Test Portal", "Stranger")
		theirs = self._statement(other.name)
		frappe.set_user(self.email)

		names = [row.name for row in self._context().statements]

		self.assertNotIn(theirs.name, names)

	def test_household_statement_is_visible_to_the_spouse(self):
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Portal Household"}).insert(
			ignore_permissions=True
		)
		spouse = make_person("_Test Portal", "Spouse", family=family.name)
		self.person.family = family.name
		self.person.save(ignore_permissions=True)
		household = self._statement(spouse.name, family=family.name)

		frappe.set_user(self.email)
		names = [row.name for row in self._context().statements]

		self.assertIn(household.name, names, "a household statement belongs to every member")

	def test_opening_someone_elses_statement_is_refused(self):
		theirs = self._statement(make_person("_Test Portal", "Other").name)
		frappe.set_user(self.email)
		frappe.local.form_dict = frappe._dict(name=theirs.name)

		with self.assertRaises(PermissionError):
			self._context()

	def test_opening_own_statement_loads_it(self):
		mine = self._statement(self.person.name)
		frappe.set_user(self.email)
		frappe.local.form_dict = frappe._dict(name=mine.name)

		self.assertEqual(self._context().statement.name, mine.name)

	def test_user_without_a_person_record_gets_an_empty_list(self):
		stranger = ensure_user("_test_statement_nobody@example.com", "Nobody")
		frappe.set_user(stranger)

		context = self._context()

		self.assertIsNone(context.person)
		self.assertEqual(context.statements, [])
