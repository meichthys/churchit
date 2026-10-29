# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	CHILD_SAFETY,
	CHURCH_NEWS,
	PASTORAL_CARE,
	create_communication_purposes,
)
from churchit.tests.helpers import RollbackEachTest


class TestCommunicationPurpose(RollbackEachTest):
	def test_the_starter_purposes_are_made_once(self):
		create_communication_purposes()
		create_communication_purposes()
		for purpose in (CHURCH_NEWS, PASTORAL_CARE, CHILD_SAFETY):
			self.assertEqual(frappe.db.count("Communication Purpose", {"purpose": purpose}), 1)

	def test_the_purposes_the_app_sends_with_cannot_be_deleted(self):
		create_communication_purposes()
		for purpose in (CHURCH_NEWS, CHILD_SAFETY):
			with self.assertRaisesRegex(frappe.ValidationError, "used by the app"):
				frappe.delete_doc("Communication Purpose", purpose)

	def test_a_purpose_the_church_added_can_be_deleted(self):
		frappe.get_doc({"doctype": "Communication Purpose", "purpose": "_Test Youth News"}).insert()
		frappe.delete_doc("Communication Purpose", "_Test Youth News")
		self.assertFalse(frappe.db.exists("Communication Purpose", "_Test Youth News"))
