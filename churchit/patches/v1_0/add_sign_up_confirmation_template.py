# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Sign-Up Confirmation Email Template. A site's own copy stays."""

import json
from pathlib import Path

import frappe

FOLDER = "sign_up_confirmation_template"


def execute():
	folder = Path(frappe.get_app_path("churchit", "church_communications", "email_template", FOLDER))
	values = json.loads((folder / f"{FOLDER}.json").read_text())
	if not frappe.db.exists("Email Template", values["name"]):
		frappe.get_doc(values).insert(ignore_permissions=True)
