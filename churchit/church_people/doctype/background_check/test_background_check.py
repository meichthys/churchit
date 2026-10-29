# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.email.doctype.notification.notification import get_context
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_years, nowdate

from churchit.church_people.doctype.background_check.background_check import (
	expire_background_checks,
	is_cleared,
)
from churchit.church_people.doctype.background_check_type.background_check_type import (
	CHILD_SAFETY_TRAINING,
	create_background_check_types,
)
from churchit.tests.helpers import RollbackEachTest, ensure, make_person
from churchit.tests.test_notification_templates import shipped_templates


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

	def test_cleared_means_every_named_type_is_current_on_the_day(self):
		other_type = ensure("Background Check Type", {"type": "_Test Other"})
		self._check(status="Cleared", completed_on=nowdate(), expires_on=add_days(nowdate(), 10))

		self.assertTrue(is_cleared(self.person, nowdate()))
		self.assertTrue(is_cleared(self.person, nowdate(), [self.check_type]))
		self.assertFalse(is_cleared(self.person, nowdate(), [self.check_type, other_type]))
		self.assertFalse(is_cleared(self.person, add_days(nowdate(), 11), [self.check_type]))


class TestCheckTypes(RollbackEachTest):
	def test_child_safety_training_is_seeded_and_a_churchs_change_survives_a_rerun(self):
		create_background_check_types()
		self.assertEqual(
			frappe.db.get_value("Background Check Type", CHILD_SAFETY_TRAINING, "valid_for_years"), 2
		)

		frappe.db.set_value("Background Check Type", CHILD_SAFETY_TRAINING, "valid_for_years", 1)
		create_background_check_types()

		self.assertEqual(
			frappe.db.get_value("Background Check Type", CHILD_SAFETY_TRAINING, "valid_for_years"), 1
		)
		self.assertEqual(frappe.db.count("Background Check Type", {"name": CHILD_SAFETY_TRAINING}), 1)


class TestBackgroundCheckExpiring(RollbackEachTest):
	def check(self, status, expires_in_days):
		return frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": make_person("_Test Expiring", status).name,
				"check_type": ensure("Background Check Type", {"type": "_Test Expiring Type"}),
				"status": status,
				"completed_on": nowdate(),
				"expires_on": add_days(nowdate(), expires_in_days),
				"provider": "_Test Provider",
			}
		).insert(ignore_permissions=True)

	def test_the_notice_names_the_person_type_and_date(self):
		check = self.check("Cleared", 30)
		notification, markdown = shipped_templates("church_communications", "Background Check Expiring")

		self.assertEqual(notification["message"], markdown)
		for template in (notification["subject"], notification["message"]):
			rendered = frappe.render_template(template, get_context(check))
			self.assertIn("_Test Expiring Cleared", rendered)
			self.assertIn("_Test Expiring Type", rendered)
		self.assertIn(
			frappe.utils.formatdate(check.expires_on),
			frappe.render_template(notification["message"], get_context(check)),
		)

	def test_it_goes_out_30_days_before_a_cleared_check_expires(self):
		due = self.check("Cleared", 30)
		later = self.check("Cleared", 31)
		pending = self.check("Pending", 30)
		notice = frappe.get_doc("Notification", "Background Check Expiring")

		found = [doc.name for doc in notice.get_documents_for_today()]

		self.assertIn(due.name, found)
		self.assertNotIn(later.name, found)
		self.assertNotIn(pending.name, found)
		self.assertFalse(notice.enabled)
