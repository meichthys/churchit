# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every way personal data leaves the desk as a file or a print writes an Access Log entry.

Frappe logs a list or Report Builder export, a print and a PDF itself, and a report's Export and Print from
the browser. These tests hold it to that for people, and cover the exports Churchit logs: the Church
Directory PDF and Data Import's Export Data.
"""

import json

import frappe
from frappe.desk.reportview import export_query
from frappe.handler import execute_cmd
from frappe.tests.classes.context_managers import patch_hooks

from churchit.church_people.report.church_directory_report.church_directory_report import (
	download_directory_pdf,
)
from churchit.tests.helpers import RollbackEachTest, make_person

DOWNLOAD_TEMPLATE = "frappe.core.doctype.data_import.data_import.download_template"


def count_access_logs(**filters):
	return frappe.db.count("Access Log", {"user": frappe.session.user, **filters})


class TestAccessLog(RollbackEachTest):
	def setUp(self):
		super().setUp()
		self.person = make_person(
			"_Test Access", "Log", emails=[{"email_address": "access.log@example.com"}]
		).name

	def test_a_list_or_report_builder_export_is_logged(self):
		before = count_access_logs(export_from="Person", file_type="CSV")
		frappe.local.form_dict = frappe._dict(
			doctype="Person",
			fields=json.dumps(["`tabPerson`.`name`", "`tabPerson`.`full_name`"]),
			filters=json.dumps([["Person", "name", "=", self.person]]),
			file_format_type="CSV",
			title="Person",
		)
		self.addCleanup(setattr, frappe.local, "form_dict", frappe._dict())

		export_query()

		self.assertEqual(count_access_logs(export_from="Person", file_type="CSV"), before + 1)

	def test_printing_a_person_is_logged_with_its_print_format(self):
		for print_format in ("Mailing Label", "Church Directory", "Standard"):
			with self.subTest(print_format):
				filters = {"reference_document": self.person, "page": f"Print Format: {print_format}"}
				before = count_access_logs(**filters)

				frappe.get_print("Person", self.person, print_format)

				self.assertEqual(count_access_logs(**filters), before + 1)

	def test_the_church_directory_pdf_is_logged(self):
		before = count_access_logs(report_name="Church Directory Report", file_type="PDF")

		download_directory_pdf(show_email=1)

		self.assertEqual(
			count_access_logs(report_name="Church Directory Report", file_type="PDF"), before + 1
		)

	def test_data_import_export_data_is_logged_only_with_records(self):
		filters = {"export_from": "Person", "method": "Export Data"}
		before = count_access_logs(**filters)
		export_fields = json.dumps({"Person": ["name", "first_name"], "emails": ["email_address"]})

		export_data(export_fields, "blank_template")
		self.assertEqual(count_access_logs(**filters), before)

		export_data(export_fields, "all")
		self.assertEqual(count_access_logs(**filters), before + 1)
		self.assertIn("access.log@example.com", frappe.response.result)


def export_data(export_fields, export_records):
	"""What the Export Data dialog sends, through the override hooks.py registers."""
	frappe.local.form_dict = frappe._dict(
		doctype="Person", export_fields=export_fields, export_records=export_records, file_type="CSV"
	)
	frappe.local.request = frappe._dict(method="POST")
	overrides = {DOWNLOAD_TEMPLATE: ["churchit.exports.download_template"]}
	try:
		with patch_hooks({"override_whitelisted_methods": overrides}):
			execute_cmd(DOWNLOAD_TEMPLATE)
	finally:
		frappe.local.form_dict = frappe._dict()
		del frappe.local.request
