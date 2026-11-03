# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.utils import nowdate

from churchit.church_people.privacy import anonymize
from churchit.tests.helpers import RollbackEachTest, ensure, make_person

# Frappe skips Version rows while it runs tests, unless a save asks for them.
SAVE_WITH_HISTORY = {"ignore_permissions": True, "ignore_version": False}


class TestCareHistory(RollbackEachTest):
	"""The records of pastoral care keep a change history, and it goes with the person's personal data."""

	def test_a_care_record_keeps_its_changes_until_the_person_is_anonymized(self):
		caregiver = make_person("_Test Care", "Giver").name
		# doctype: (values to create it with, field to change, new value)
		records = {
			"Care Request": (
				{"category": ensure("Care Request Type", {"type": "_Test Need"}), "description": "Meals"},
				"description",
				"Meals and a ride",
			),
			"Care Assignment": ({"deacon": caregiver, "start_date": nowdate()}, "notes", "Weekly call"),
			"Visitation Log": (
				{"visit_type": ensure("Visit Type", {"type": "_Test Visit"})},
				"notes",
				"At home",
			),
			"Member Transfer": ({"direction": "Out"}, "other_church", "Grace Church"),
		}
		for doctype, (values, fieldname, new_value) in records.items():
			with self.subTest(doctype):
				person = make_person("_Test Care", doctype).name
				doc = frappe.get_doc({"doctype": doctype, "person": person, **values}).insert(
					ignore_permissions=True
				)
				doc.set(fieldname, new_value)
				doc.save(**SAVE_WITH_HISTORY)
				filters = {"ref_doctype": doctype, "docname": doc.name}
				self.assertTrue(frappe.db.exists("Version", filters), "the change is in the history")

				anonymize(person)

				self.assertFalse(frappe.db.exists("Version", filters))
