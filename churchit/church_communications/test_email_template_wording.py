# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import json
from pathlib import Path
from unittest.mock import patch

import frappe

from churchit.church_finances.doctype.online_donation.test_online_donation import (
	ensure_online_payment_type,
	log_charge,
	make_gift,
)
from churchit.church_foundations.doctype.church.church import church_name
from churchit.patches.v1_0 import word_receipt_and_sign_offs_in_email_templates as patch_module
from churchit.tests.helpers import RollbackEachTest, ensure_root_church

ROOT = Path(frappe.get_app_path("churchit", "church_communications", "email_template"))


def shipped(folder: str) -> dict:
	return json.loads((ROOT / folder / f"{folder}.json").read_text())


def restore_old_text() -> None:
	"""Give each template the text the patch replaces."""
	for folder, html in patch_module.SHIPPED.items():
		values = shipped(folder)
		if frappe.db.exists("Email Template", values["name"]):
			frappe.db.set_value("Email Template", values["name"], "response_html", html)
		else:
			frappe.get_doc({**values, "response_html": html}).insert(ignore_permissions=True)


class TestEmailTemplateWording(RollbackEachTest):
	def test_the_patch_replaces_the_shipped_text(self):
		restore_old_text()

		patch_module.execute()

		for folder in patch_module.SHIPPED:
			values = shipped(folder)
			self.assertEqual(
				frappe.db.get_value("Email Template", values["name"], "response_html"),
				values["response_html"],
			)

	def test_the_patch_keeps_a_church_s_own_words(self):
		restore_old_text()
		frappe.db.set_value("Email Template", "Sign-Up Reminder", "response_html", "<p>Ours</p>")

		patch_module.execute()

		self.assertEqual(
			frappe.db.get_value("Email Template", "Sign-Up Reminder", "response_html"), "<p>Ours</p>"
		)

	def test_the_receipt_names_the_fund_and_claims_no_attachment(self):
		restore_old_text()
		patch_module.execute()
		ensure_online_payment_type()
		fund = frappe.get_doc({"doctype": "Fund", "fund": "_Test Receipt Fund"}).insert(
			ignore_permissions=True
		)
		gift = make_gift(fund.name, 50, donor_name="Ruth Giver", email="ruth.giver@example.com")
		log_charge(gift)

		with patch.object(frappe, "sendmail") as sendmail:
			gift.send_acknowledgment()

		message = sendmail.call_args.kwargs["message"]
		self.assertIn("_Test Receipt Fund fund on", message)
		self.assertNotIn("attached", message)
		self.assertNotIn("Treasury Team", message)


class TestChurchNameInEmailDialog(RollbackEachTest):
	def test_frappe_s_email_dialog_signs_with_the_church_of_the_document(self):
		"""Frappe fills a template with the document's fields; church_name would print the Jinja method."""
		church = ensure_root_church()
		template = frappe.get_doc(
			{
				"doctype": "Email Template",
				"name": "_Test Church Name Sign-Off",
				"subject": "Hello from {{ church_name }}",
				"use_html": 1,
				"response_html": "<p>{{ first_name }}, from {{ church_name }}</p>",
			}
		).insert(ignore_permissions=True)

		email = template.get_formatted_email(
			json.dumps({"doctype": "Person", "first_name": "Ann", "church": church})
		)

		self.assertEqual(email["message"], f"<p>Ann, from {church_name({'church': church})}</p>")
		self.assertNotIn("function", email["subject"])
