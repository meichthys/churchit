# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Give existing sites the Giving Statement Email Template that statement emails use. A site's own copy stays."""

import json
from pathlib import Path

import frappe

FOLDER = "giving_statement_template"


def execute():
	path = Path(
		frappe.get_app_path("churchit", "church_communications", "email_template", FOLDER, f"{FOLDER}.json")
	)
	values = json.loads(path.read_text())
	if not frappe.db.exists("Email Template", values["name"]):
		frappe.get_doc(values).insert(ignore_permissions=True)
