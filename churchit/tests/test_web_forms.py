# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The web forms the church website keeps for visitors. Members use the member app instead."""

import json
from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.patches.v1_0 import remove_member_web_forms
from churchit.tests.helpers import RollbackEachTest


class TestFormEndings(FrappeTestCase):
	def test_the_visitor_forms_end_on_the_home_page(self):
		"""Frappe's survey buttons ("Submit another response") are not what a visitor expects."""
		for module, name, route in (
			("church_prayers", "prayer_request_anonymous", "prayer-request-anonymous"),
			("church_people", "connection_card", "connection-card"),
		):
			path = Path(frappe.get_app_path("churchit", module, "web_form", name, f"{name}.json"))
			form = json.loads(path.read_text())

			self.assertEqual(form["route"], route)
			self.assertEqual(form["success_url"], "/", name)


class TestRemoveMemberWebForms(RollbackEachTest):
	"""The patch that deletes the member web forms on existing sites."""

	def set_form(self, name, is_standard):
		"""Make Web Form *name* exist, as the app shipped it (standard) or as a church made it."""
		if not frappe.db.exists("Web Form", name):
			frappe.get_doc(
				{"doctype": "Web Form", "name": name, "title": name, "route": name, "doc_type": "Pledge"}
			).insert(ignore_permissions=True)
		# Not on insert: saving a standard form on a developer-mode site writes its files into the app.
		frappe.db.set_value("Web Form", name, "is_standard", is_standard)

	def test_the_shipped_member_forms_go_and_a_second_run_changes_nothing(self):
		for name in remove_member_web_forms.WEB_FORMS:
			self.set_form(name, 1)

		remove_member_web_forms.execute()
		remove_member_web_forms.execute()

		self.assertEqual(
			frappe.get_all("Web Form", filters={"name": ("in", remove_member_web_forms.WEB_FORMS)}), []
		)

	def test_a_form_the_church_made_stays(self):
		self.set_form("pledge", 0)
		remove_member_web_forms.execute()
		self.assertTrue(frappe.db.exists("Web Form", "pledge"))

	def test_no_form_the_app_still_ships_is_deleted(self):
		shipped = Path(frappe.get_app_path("churchit")).glob("*/web_form/*/*.json")
		names = {json.loads(path.read_text())["name"] for path in shipped}
		self.assertTrue(names)
		self.assertFalse(names & set(remove_member_web_forms.WEB_FORMS))
