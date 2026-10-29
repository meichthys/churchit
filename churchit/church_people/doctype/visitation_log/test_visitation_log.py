# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase


class TestVisitationLog(FrappeTestCase):
	def test_a_new_visit_starts_on_a_visit_type_that_exists(self):
		"""A default naming an unseeded Visit Type stopped every new visit from saving until it was changed."""
		visit_type = frappe.new_doc("Visitation Log").visit_type
		self.assertTrue(not visit_type or frappe.db.exists("Visit Type", visit_type))
