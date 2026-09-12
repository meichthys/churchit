# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import ensure, make_function, make_person
from churchit.utils import resolve_link_titles, set_report_link_titles


class TestSetReportLinkTitles(FrappeTestCase):
	def setUp(self):
		self.person = make_person("_Test Title", "Holder")
		self.function = make_function("_Test Titled Function")

	def test_link_columns_get_a_title_key_without_changing_the_value(self):
		columns = [{"fieldname": "person", "fieldtype": "Link", "options": "Person"}]
		data = [{"person": self.person.name}, {"person": None}]
		set_report_link_titles(columns, data)

		self.assertEqual(data[0]["person"], self.person.name)
		self.assertEqual(data[0]["_person_link_title"], "_Test Title Holder")
		self.assertNotIn("_person_link_title", data[1])

	def test_doctypes_whose_title_is_their_name_are_skipped(self):
		columns = [{"fieldname": "type", "fieldtype": "Link", "options": "Function Type"}]
		data = [{"type": self.function.type}]
		set_report_link_titles(columns, data)
		self.assertNotIn("_type_link_title", data[0])

	def test_dynamic_link_columns_resolve_per_doctype(self):
		columns = [{"fieldname": "recipient", "fieldtype": "Dynamic Link", "options": "recipient_type"}]
		data = [
			{"recipient_type": "Person", "recipient": self.person.name},
			{"recipient_type": "Function", "recipient": self.function.name},
			{"recipient_type": "Not A DocType", "recipient": "x"},
		]
		set_report_link_titles(columns, data)

		self.assertEqual(data[0]["_recipient_link_title"], "_Test Title Holder")
		self.assertEqual(data[1]["_recipient_link_title"], self.function.title)
		self.assertNotIn("_recipient_link_title", data[2])

	def test_empty_data_is_left_alone(self):
		data = []
		set_report_link_titles([{"fieldname": "person", "fieldtype": "Link", "options": "Person"}], data)
		self.assertEqual(data, [])


class TestResolveLinkTitles(FrappeTestCase):
	def setUp(self):
		self.person = make_person("_Test Resolve", "Person")
		self.request_type = ensure("Prayer Request Type", {"type": "Health"})

	def test_links_and_dynamic_links_are_replaced_in_place(self):
		rows = [
			frappe._dict(
				requestor=self.person.name,
				type=self.request_type,
				recipient_type="Person",
				recipient=self.person.name,
			)
		]
		resolve_link_titles(rows, "Prayer Request")

		self.assertEqual(rows[0].requestor, "_Test Resolve Person")
		self.assertEqual(rows[0].recipient, "_Test Resolve Person")
		# Prayer Request Type is named by its title, so it stays as is.
		self.assertEqual(rows[0].type, self.request_type)

	def test_unknown_values_are_left_untouched(self):
		rows = [frappe._dict(requestor="PRSN-DOES-NOT-EXIST", recipient_type=None, recipient=None)]
		resolve_link_titles(rows, "Prayer Request")
		self.assertEqual(rows[0].requestor, "PRSN-DOES-NOT-EXIST")
