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

from churchit.setup import sample_data

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
	"Bible Verse",
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
		self.assertEqual(types[sample_data._CHURCH_MANAGER_EMAIL], "System User")
		self.assertEqual(types[sample_data._CHURCH_MEMBER_EMAIL], "Website User")

	def test_the_member_has_giving_to_show_on_a_statement(self):
		person = frappe.db.get_value("Person", {"user": sample_data._CHURCH_MEMBER_EMAIL}, "name")
		self.assertTrue(
			frappe.db.exists("Donation", {"person": person, "parenttype": "Collection"}),
			"the demo member needs gifts, or their statement renders empty",
		)

	def test_collections_are_submitted_so_funds_carry_a_balance(self):
		self.assertTrue(frappe.db.exists("Collection", {"docstatus": 1}))
		self.assertTrue(any(frappe.get_all("Fund", pluck="balance")))


class TestSampleDataRoundTrip(FrappeTestCase):
	"""Its own class so the wipe below does not strand the loader tests above.

	delete_sample_data() runs on unfiltered doctypes, so it clears every record of
	them on whatever site the suite runs against, not only the seeded ones.
	"""

	def test_delete_removes_what_create_made(self):
		sample_data.create_sample_data()
		sample_data.delete_sample_data()

		# Ministry is the one step with a filter: the General ministry predates the
		# sample data and is meant to survive.
		remaining = [
			doctype for doctype in SEEDED_DOCTYPES if doctype != "Ministry" and frappe.db.count(doctype)
		]
		self.assertEqual(remaining, [])
		self.assertFalse(frappe.db.exists("User", sample_data._CHURCH_MANAGER_EMAIL))

	def test_delete_removes_draft_and_submitted_expenses_alike(self):
		sample_data.create_sample_data()
		self.assertTrue(frappe.db.exists("Expense", {"docstatus": 0}))
		self.assertTrue(frappe.db.exists("Expense", {"docstatus": 1}))

		sample_data.delete_sample_data()
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
