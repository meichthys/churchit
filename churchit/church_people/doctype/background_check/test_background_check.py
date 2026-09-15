# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, nowdate

from churchit.church_people.doctype.background_check.background_check import expire_background_checks
from churchit.tests.helpers import ensure, make_person


class TestBackgroundCheck(FrappeTestCase):
	def setUp(self):
		self.check_type = ensure(
			"Background Check Type",
			{"type": "_Test Criminal"},
			{"type": "_Test Criminal", "valid_for_years": 3},
		)
		self.person = make_person("_Test Background", "Check").name

	def _check(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": self.person,
				"check_type": self.check_type,
				**values,
			}
		).insert(ignore_permissions=True)

	def test_expiry_defaults_from_the_check_type(self):
		check = self._check(status="Cleared", completed_on=nowdate())
		self.assertEqual(str(check.expires_on), add_years(nowdate(), 3))

	def test_explicit_expiry_is_kept(self):
		expires_on = add_years(nowdate(), 1)
		check = self._check(status="Cleared", completed_on=nowdate(), expires_on=expires_on)
		self.assertEqual(str(check.expires_on), expires_on)

	def test_types_without_validity_never_expire(self):
		check_type = ensure(
			"Background Check Type",
			{"type": "_Test Permanent"},
			{"type": "_Test Permanent", "valid_for_years": 0},
		)
		check = self._check(check_type=check_type, status="Cleared", completed_on=nowdate())
		self.assertIsNone(check.expires_on)

	def test_a_result_needs_a_completed_date(self):
		self.assertRaises(frappe.ValidationError, self._check, status="Cleared")

	def test_cleared_check_past_its_expiry_is_saved_as_expired(self):
		check = self._check(
			status="Cleared",
			completed_on=add_years(nowdate(), -4),
			expires_on=add_days(nowdate(), -1),
		)
		self.assertEqual(check.status, "Expired")

	def test_scheduler_expires_cleared_checks(self):
		check = self._check(status="Cleared", completed_on=nowdate())
		frappe.db.set_value("Background Check", check.name, "expires_on", add_days(nowdate(), -1))
		pending = self._check(status="Pending", expires_on=add_days(nowdate(), -1))

		expire_background_checks()

		self.assertEqual(frappe.db.get_value("Background Check", check.name, "status"), "Expired")
		self.assertEqual(frappe.db.get_value("Background Check", pending.name, "status"), "Pending")

	def test_person_name_is_fetched(self):
		check = self._check()
		self.assertEqual(check.person_name, "_Test Background Check")
