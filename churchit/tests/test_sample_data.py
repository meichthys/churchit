# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The sample data loader behind the setup wizard opt-in and the Settings workspace link.

The loader inserts through the normal document API across nearly every module, so
these double as an integration check: a validation added anywhere that the sample
records violate surfaces here rather than on a new user's first install.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_finances.doctype.giving_statement.giving_statement import generate_statements
from churchit.church_people.report.person_anniversaries_this_month import (
	person_anniversaries_this_month as anniversaries_this_month,
)
from churchit.church_people.report.person_positions_ending_this_month import (
	person_positions_ending_this_month as positions_ending_this_month,
)
from churchit.setup import sample_data
from churchit.tests.helpers import ensure_root_church

# One or two doctypes per module, enough to prove each section of the loader ran.
SEEDED_DOCTYPES = (
	"Person",
	"Family",
	"Missionary",
	"Missionary Agency",
	"Fund",
	"Expense",
	"Collection",
	"Budget",
	"Function",
	"Group",
	"Ministry",
	"Prayer Request",
	"Prayer",
	"Bible Memory Item",
	"Sermon",
	"Belief",
	"Location",
	"Room",
	"Church Asset",
	"Church Task",
	"Song",
	"Meeting Minutes",
)


def counts():
	return {doctype: frappe.db.count(doctype) for doctype in SEEDED_DOCTYPES}


class TestSampleDataLoader(FrappeTestCase):
	"""Loaded once for the class: the test transaction spans every method here."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sample_data.create_sample_data()

	def test_seeds_every_module(self):
		empty = [doctype for doctype in SEEDED_DOCTYPES if not frappe.db.count(doctype)]
		self.assertEqual(empty, [], "loader produced no records for these doctypes")

	def test_running_twice_adds_nothing(self):
		"""The module docstring promises a second run is safe."""
		before = counts()
		sample_data.create_sample_data()
		self.assertEqual(counts(), before)

	def test_demo_passwords_are_the_email_on_every_run(self):
		from frappe.utils.password import check_password

		frappe.utils.password.update_password(sample_data._CHURCH_MANAGER_EMAIL, "something-else")
		sample_data.create_sample_data()
		self.assertEqual(
			check_password(sample_data._CHURCH_MANAGER_EMAIL, sample_data._CHURCH_MANAGER_EMAIL),
			sample_data._CHURCH_MANAGER_EMAIL,
		)

	def test_demo_logins_are_linked_to_their_person(self):
		for email, person, _role_profile in sample_data._SAMPLE_USERS:
			self.assertTrue(frappe.db.exists("User", email), f"{email} was not created")
			linked = frappe.db.get_value("Person", {"user": email}, "full_name")
			self.assertEqual(linked, person, f"{email} is linked to the wrong Person")

	def test_demo_logins_cover_both_staff_and_a_plain_member(self):
		"""A member account is the only way to see the portal, since staff are
		System Users and Frappe hides its /me Portal link from them."""
		types = {
			email: frappe.db.get_value("User", email, "user_type")
			for email, _person, _profile in sample_data._SAMPLE_USERS
		}
		self.assertEqual(types.pop(sample_data._CHURCH_MEMBER_EMAIL), "Website User")
		self.assertEqual(set(types.values()), {"System User"})

	def test_the_member_has_giving_to_show_on_a_statement(self):
		person = frappe.db.get_value("Person", {"user": sample_data._CHURCH_MEMBER_EMAIL}, "name")
		self.assertTrue(
			frappe.db.exists("Donation", {"person": person, "parenttype": "Collection"}),
			"the demo member needs gifts, or their statement renders empty",
		)

	def test_the_monthly_people_reports_always_have_a_row(self):
		"""Fixed dates left these empty for eleven months of the year."""
		for report in (anniversaries_this_month, positions_ending_this_month):
			_columns, rows = report.execute({})
			self.assertTrue(rows, f"{report.__name__} is empty after loading sample data")

	def test_a_group_is_public_so_the_portal_has_something_to_join(self):
		self.assertTrue(frappe.db.exists("Group", {"public": 1, "show_in_portal": 1}))

	def test_collections_are_submitted_so_funds_carry_a_balance(self):
		self.assertTrue(frappe.db.exists("Collection", {"docstatus": 1}))
		self.assertTrue(any(frappe.get_all("Fund", pluck="balance")))


class TestSampleDataRoundTrip(FrappeTestCase):
	"""A wipe, one load and one wipe for the whole class, then what the wipe had to leave behind.

	Its own class so the wipe does not strand the loader tests above.
	delete_sample_data() runs on unfiltered doctypes, so it clears every record of
	them on whatever site the suite runs against, not only the seeded ones. The
	first wipe makes the load start from nothing, as on a new site, even when the
	site already has sample data.

	The round trip is in setUpClass because a load and a wipe cost seconds each:
	one cycle, with what each test needs recorded on the way past, buys the same
	coverage as a cycle per test.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sample_data.delete_sample_data()
		sample_data.create_sample_data()
		cls.home_addresses = frappe.get_all(
			"Address", {"address_title": ["in", list(sample_data._HOME_ADDRESSES)]}, pluck="name"
		)
		cls.linked_home_addresses = frappe.db.count("Postal Address", {"address": ["in", cls.home_addresses]})
		generate_statements("2000-01-01", "2100-12-31")
		cls.statements = frappe.db.count("Giving Statement")
		cls.draft_expense = bool(frappe.db.exists("Expense", {"docstatus": 0}))
		cls.submitted_expense = bool(frappe.db.exists("Expense", {"docstatus": 1}))
		cls.function_type = cls.add_records_a_user_would_make()

		sample_data.delete_sample_data()

	@classmethod
	def add_records_a_user_would_make(cls):
		"""Records nothing seeds but that link to sample records, so the wipe has to take them too."""
		person = frappe.get_all("Person", limit=1, pluck="name")[0]
		fund = frappe.get_all("Fund", limit=1, pluck="name")[0]
		function = frappe.get_all("Function", limit=1, pluck="name")[0]
		check_type = frappe.get_all("Background Check Type", limit=1, pluck="name")[0]
		frappe.get_doc({"doctype": "Bulletin", "function": function}).insert()
		frappe.get_doc({"doctype": "Online Donation", "person": person, "fund": fund, "amount": 5}).insert()
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": person,
				"check_type": check_type,
				"status": "Requested",
				"requested_on": frappe.utils.today(),
			}
		).insert()

		function_type = frappe.get_all("Function Type", limit=1, pluck="name")[0]
		frappe.db.set_value("Function Type", function_type, "template_function", function)
		return function_type

	def test_delete_removes_what_create_made(self):
		# Ministry is the one step with a filter: the General ministry predates the
		# sample data and is meant to survive.
		remaining = [
			doctype for doctype in SEEDED_DOCTYPES if doctype != "Ministry" and frappe.db.count(doctype)
		]
		self.assertEqual(remaining, [])
		self.assertFalse(frappe.db.exists("User", sample_data._CHURCH_MANAGER_EMAIL))

	def test_families_and_people_without_one_get_a_home_address_that_delete_removes(self):
		self.assertEqual(len(self.home_addresses), len(sample_data._HOME_ADDRESSES))
		self.assertEqual(self.linked_home_addresses, len(sample_data._HOME_ADDRESSES))
		self.assertFalse(frappe.db.exists("Address", {"name": ["in", self.home_addresses]}))

	def test_delete_leaves_the_church_saveable(self):
		"""The Church survives the wipe; a link left pointing into it would strand the record."""
		frappe.get_doc("Church", ensure_root_church()).save(ignore_permissions=True)

	def test_delete_removes_statements_issued_from_sample_giving(self):
		"""Statements are generated, not seeded, but link to sample people, families
		and funds; leaving them behind strands those links as raw IDs."""
		self.assertTrue(self.statements, "the sample giving issued no statements to wipe")
		self.assertEqual(frappe.db.count("Giving Statement"), 0)

	def test_delete_removes_records_that_users_make_from_sample_data(self):
		"""Not seeded, but they link to sample records and would otherwise dangle."""
		for doctype in ("Bulletin", "Online Donation", "Background Check"):
			self.assertEqual(frappe.db.count(doctype), 0, doctype)
		self.assertFalse(frappe.db.get_value("Function Type", self.function_type, "template_function"))

	def test_delete_removes_draft_and_submitted_expenses_alike(self):
		self.assertTrue(self.draft_expense, "the sample data seeded no draft expense to wipe")
		self.assertTrue(self.submitted_expense, "the sample data seeded no submitted expense to wipe")
		self.assertEqual(frappe.db.count("Expense"), 0)


class TestSetupWizardHook(FrappeTestCase):
	"""The opt-in gate, checked without paying for a full load."""

	def test_creates_when_opted_in(self):
		with patch.object(sample_data, "create_sample_data") as create:
			sample_data.setup_wizard_complete({"create_sample_data": 1})
		create.assert_called_once()

	def test_skips_when_not_opted_in(self):
		with patch.object(sample_data, "create_sample_data") as create:
			sample_data.setup_wizard_complete({})
			sample_data.setup_wizard_complete({"create_sample_data": 0})
			sample_data.setup_wizard_complete(None)
		create.assert_not_called()
