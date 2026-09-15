# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import make_person


class TestPrayer(FrappeTestCase):
	"""before_save builds the title, which is what link fields and lists show."""

	def setUp(self):
		self.person = make_person("_Test Prayer", "Intercessor")

	def _prayer(self, **values):
		return frappe.get_doc(
			{"doctype": "Prayer", "person": self.person.name, "date": "2031-05-01 09:30:00", **values}
		).insert(ignore_permissions=True)

	def test_title_joins_person_and_date(self):
		prayer = self._prayer()
		self.assertEqual(prayer.title, f"{self.person.name} - 2031-05-01 09:30:00")

	def test_title_is_rebuilt_when_the_date_changes(self):
		prayer = self._prayer()
		prayer.date = "2031-06-02 14:00:00"
		prayer.save(ignore_permissions=True)
		self.assertEqual(prayer.title, f"{self.person.name} - 2031-06-02 14:00:00")
