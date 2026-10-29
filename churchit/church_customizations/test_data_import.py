# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.core.doctype.data_import.importer import INSERT

from churchit.church_foundations.church_access import set_user_church
from churchit.tests.helpers import RollbackEachTest, ensure_user, make_two_churches


class TestDataImportPermissions(RollbackEachTest):
	"""A Data Import has no church, and its file holds every row, so a Church Manager opens only their own."""

	def test_a_church_manager_cannot_open_another_managers_import_or_its_file(self):
		_root, branch_a, branch_b = make_two_churches()
		manager_a, manager_b = (
			ensure_user(f"_test_import_perm_{key}@example.com", key, roles=("Church Manager",))
			for key in ("a", "b")
		)
		set_user_church(manager_a, branch_a)
		set_user_church(manager_b, branch_b)
		frappe.set_user(manager_a)
		data_import = frappe.get_doc(
			{"doctype": "Data Import", "reference_doctype": "People Import", "import_type": INSERT}
		).insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"_test_import_perm_{frappe.generate_hash(length=8)}.csv",
				"content": "First Name,Medical Notes\nAnn,Peanuts",
				"is_private": 1,
				"attached_to_doctype": "Data Import",
				"attached_to_name": data_import.name,
				"attached_to_field": "import_file",
			}
		).insert()

		frappe.set_user(manager_b)
		self.assertNotIn(data_import.name, frappe.get_list("Data Import", pluck="name"))
		self.assertFalse(frappe.has_permission("Data Import", "read", doc=data_import.name))
		self.assertFalse(frappe.has_permission("File", "read", doc=file.name))

		frappe.set_user(manager_a)
		self.assertIn(data_import.name, frappe.get_list("Data Import", pluck="name"))
		self.assertTrue(frappe.has_permission("Data Import", "write", doc=data_import.name))
		self.assertTrue(frappe.has_permission("File", "read", doc=file.name))
