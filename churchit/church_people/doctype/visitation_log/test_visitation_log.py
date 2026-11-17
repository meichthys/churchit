# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.doctype.people_settings.people_settings import create_reminders
from churchit.church_people.privacy import anonymize_person
from churchit.patches.v1_0.fill_care_record_person_names import DOCTYPES, execute
from churchit.tests.helpers import RollbackEachTest, make_person


class TestVisitationLog(FrappeTestCase):
	def test_a_new_visit_starts_on_a_visit_type_that_exists(self):
		"""A default naming an unseeded Visit Type stopped every new visit from saving until it was changed."""
		visit_type = frappe.new_doc("Visitation Log").visit_type
		self.assertTrue(not visit_type or frappe.db.exists("Visit Type", visit_type))


class TestCareRecordTitles(RollbackEachTest):
	def test_each_care_record_is_titled_with_the_persons_name(self):
		for doctype in DOCTYPES:
			meta = frappe.get_meta(doctype)
			self.assertEqual(meta.title_field, "person_name", doctype)
			self.assertTrue(meta.show_title_field_in_link, doctype)

	def test_a_visit_takes_the_persons_name_and_the_patch_fills_older_ones(self):
		person = make_person("_Test Visited", "Person")
		visit = frappe.get_doc(
			{
				"doctype": "Visitation Log",
				"person": person.name,
				"visit_type": frappe.get_all("Visit Type", pluck="name")[0],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(visit.person_name, person.full_name)

		frappe.db.set_value("Visitation Log", visit.name, "person_name", None)
		execute()

		self.assertEqual(frappe.db.get_value("Visitation Log", visit.name, "person_name"), person.full_name)

	def test_forgetting_the_person_clears_the_name_copy(self):
		person = make_person("_Test Forgotten", "Visitee")
		visit = frappe.get_doc(
			{
				"doctype": "Visitation Log",
				"person": person.name,
				"visit_type": frappe.get_all("Visit Type", pluck="name")[0],
			}
		).insert(ignore_permissions=True)

		anonymize_person(person.name)

		self.assertNotIn("Forgotten", frappe.db.get_value("Visitation Log", visit.name, "person_name") or "")

	def test_a_planned_visit_gets_the_reminder_too(self):
		create_reminders()
		condition = frappe.db.get_value("Notification", "Visitation Follow-Up Due", "condition")
		for status in ("Planned", "Scheduled"):
			self.assertTrue(frappe.safe_eval(condition, None, {"doc": frappe._dict(status=status)}))
		self.assertFalse(frappe.safe_eval(condition, None, {"doc": frappe._dict(status="Completed")}))
