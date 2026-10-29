# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Date the people already Inactive from the tracked change that made them so.

A person with no such change in their history (created Inactive, or changed
before Person tracked changes) keeps a blank Inactive Since.
"""

import json

import frappe
from frappe.utils import getdate

from churchit.church_people.membership import INACTIVE


def execute():
	undated = frappe.get_all(
		"Person", filters={"membership_status": INACTIVE, "inactive_since": ("is", "not set")}, pluck="name"
	)
	if not undated:
		return
	for name, date in get_dates_made_inactive(undated).items():
		frappe.db.set_value("Person", name, "inactive_since", date, update_modified=False)


def get_dates_made_inactive(names):
	"""The day of each person's latest tracked change of Status to Inactive."""
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Person", "docname": ("in", names), "data": ("like", "%membership_status%")},
		fields=["docname", "data", "creation"],
		order_by="creation asc",
	)
	dates = {}
	for version in versions:
		changed = json.loads(version.data).get("changed") or []
		if any(field == "membership_status" and new == INACTIVE for field, _old, new in changed):
			dates[version.docname] = getdate(version.creation)
	return dates
