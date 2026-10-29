# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Take fields that not every reader may see out of the saved Versions of each record.

The form timeline shows a record's Versions to every reader of the record, but only some roles of the
family's church may read its Authorized Pickups, and a Person's Team Calendar Key is at permlevel 4.
A merge wrote that key into a Version. A Version that held only such changes is deleted.
"""

import frappe

DIFF_KEYS = ("changed", "added", "removed", "row_changed")
PRIVATE_FIELDS = {"Family": "authorized_pickups", "Person": "team_calendar_key"}


def execute():
	for doctype, fieldname in PRIVATE_FIELDS.items():
		remove_field_from_versions(doctype, fieldname)


def remove_field_from_versions(doctype: str, fieldname: str):
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "data": ["like", f"%{fieldname}%"]},
		fields=["name", "data"],
	)
	for version in versions:
		diff = frappe.parse_json(version.data)
		for key in DIFF_KEYS:
			diff[key] = [entry for entry in diff.get(key) or [] if entry[0] != fieldname]
		if any(diff[key] for key in DIFF_KEYS):
			data = frappe.as_json(diff, indent=None, separators=(",", ":"))
			frappe.db.set_value("Version", version.name, "data", data, update_modified=False)
		else:
			frappe.db.delete("Version", version.name)
