# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.church_people.doctype.position_type.position_type import assign_position_to_person
from churchit.tests.helpers import ensure, make_person


class TestPositionType(FrappeTestCase):
	def test_assigning_a_position_keeps_a_blank_start_date(self):
		position_type = ensure("Position Type", {"position": "_Test Assigned Role"})
		person = make_person("_Test Assigned", "Role")

		assign_position_to_person(position_type, person.name)

		self.assertIsNone(frappe.db.get_value("Position", {"parent": person.name}, "start_date"))
