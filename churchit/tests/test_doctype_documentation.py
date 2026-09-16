# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every churchit doctype must link to an in-app documentation page (issue #187).

The form view shows a help icon (``public/js/help_icon_on_form.js``) that opens
``meta.documentation``; the link must point at an existing workspace.
"""

from urllib.parse import unquote

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDoctypeDocumentation(FrappeTestCase):
	def test_every_doctype_has_a_documentation_link(self):
		rows = self.doctypes()
		missing = [r.name for r in rows if not r.documentation]
		self.assertEqual(missing, [], f"Doctypes without a Documentation Link: {missing}")

	def test_documentation_links_point_to_existing_workspaces(self):
		# Mirrors frappe.router.slug()
		routes = {name.lower().replace(" ", "-") for name in frappe.get_all("Workspace", pluck="name")}
		broken = []
		for row in self.doctypes():
			if not row.documentation:
				continue
			route = unquote(row.documentation).removeprefix("/app/").split("#")[0]
			if route not in routes:
				broken.append((row.name, row.documentation))
		self.assertEqual(broken, [])

	@staticmethod
	def doctypes():
		modules = frappe.get_module_list("churchit")
		return frappe.get_all(
			"DocType", filters={"module": ["in", modules]}, fields=["name", "documentation"]
		)
