# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Counter-named doctypes must each keep their own sequence (issue #234)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.patches.v1_0.seed_naming_series_counters import get_series_doctypes
from churchit.tests.helpers import make_person


class TestNaming(FrappeTestCase):
	def test_no_counter_autoname_uses_format_prefix(self):
		"""``format:XXX-{####}`` shares one global counter across every doctype."""
		modules = frappe.get_module_list("churchit")
		rows = frappe.get_all("DocType", filters={"module": ["in", modules]}, fields=["name", "autoname"])
		offenders = [
			r.name for r in rows if r.autoname and r.autoname.startswith("format:") and "#" in r.autoname
		]
		self.assertEqual(offenders, [])

	def test_every_counter_doctype_is_recognised_by_the_seed_patch(self):
		self.assertIn(("Person", "PRSN-.####"), list(get_series_doctypes()))
		self.assertGreater(len(list(get_series_doctypes())), 30)

	def test_doctypes_increment_independently(self):
		first = make_person("_Test Naming", "One")
		family = frappe.get_doc({"doctype": "Family", "family_name": "_Test Naming"}).insert()
		second = make_person("_Test Naming", "Two")

		self.assertTrue(family.name.startswith("FAM-"))
		self.assertEqual(self.number(second.name), self.number(first.name) + 1)

	@staticmethod
	def number(name):
		return int(name.split("-")[-1])
