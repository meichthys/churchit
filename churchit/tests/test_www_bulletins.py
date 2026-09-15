# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import make_function
from churchit.www.bulletins import get_context, get_published_bulletins


class TestBulletinsPage(FrappeTestCase):
	def make_bulletin(self, function_name, publish):
		function = make_function(function_name)
		return frappe.get_doc({"doctype": "Bulletin", "function": function.name, "publish": publish}).insert(
			ignore_permissions=True
		)

	def test_lists_only_published_bulletins(self):
		shared = self.make_bulletin("_Test Shared Service", publish=1)
		private = self.make_bulletin("_Test Draft Service", publish=0)

		names = [row.name for row in get_published_bulletins()]

		self.assertIn(shared.name, names)
		self.assertNotIn(private.name, names)

	def test_guests_are_sent_to_log_in(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.Redirect, get_context, frappe._dict())
			self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/bulletins")
		finally:
			frappe.set_user("Administrator")
