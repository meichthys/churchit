# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_people.doctype.life_event_type.life_event_type import FILLS_IN_PERSON_FIELDS
from churchit.tests.helpers import RollbackEachTest, ensure


class TestLifeEventType(RollbackEachTest):
	def test_a_type_that_fills_in_person_fields_cannot_be_deleted_or_renamed(self):
		for event_type in FILLS_IN_PERSON_FIELDS:
			ensure("Life Event Type", {"type": event_type})
			with self.subTest(event_type=event_type):
				self.assertRaises(frappe.ValidationError, frappe.delete_doc, "Life Event Type", event_type)
				self.assertRaises(
					frappe.ValidationError,
					frappe.rename_doc,
					"Life Event Type",
					event_type,
					f"_Test {event_type}",
				)

	def test_another_type_can_be_renamed(self):
		ensure("Life Event Type", {"type": "_Test Graduation"})

		frappe.rename_doc("Life Event Type", "_Test Graduation", "_Test Commencement")

		self.assertTrue(frappe.db.exists("Life Event Type", "_Test Commencement"))
