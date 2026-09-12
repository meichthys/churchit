# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import make_address


class TestLocation(FrappeTestCase):
	"""A child location falls back to its parent's address, so a campus only
	has to be addressed once."""

	def setUp(self):
		self.address = make_address("_Test Campus Address")
		self.parent = self._location("_Test Campus", address=self.address.name)

	def _location(self, location_name, **values):
		return frappe.get_doc({"doctype": "Location", "location_name": location_name, **values}).insert(
			ignore_permissions=True
		)

	def test_child_inherits_the_parent_address(self):
		child = self._location("_Test Wing", parent_location=self.parent.name)
		self.assertEqual(child.address, self.address.name)

	def test_own_address_is_not_overwritten_by_the_parent(self):
		own = make_address("_Test Wing Address")
		child = self._location("_Test Annex", parent_location=self.parent.name, address=own.name)
		self.assertEqual(child.address, own.name)

	def test_location_without_a_parent_keeps_a_blank_address(self):
		orphan = self._location("_Test Standalone")
		self.assertFalse(orphan.address)
