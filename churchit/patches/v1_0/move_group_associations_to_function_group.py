# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Move each Function's first Group association row into its Group field.

Only rows of type Group move, and only one per Function: the first group of the Function's own
church, or of no church. Other Group rows stay, and a Comment on the Function names them. A
Function that has a group already, or is shared, is left alone, so a second run changes nothing.
"""

import frappe
from frappe import _

from churchit.church_scope import default_church


def execute():
	rows = frappe.get_all(
		"Function Association",
		filters={"parenttype": "Function", "parentfield": "associations", "association_type": "Group"},
		fields=["name", "parent", "association"],
		order_by="parent asc, idx asc",
	)
	by_function = {}
	for row in rows:
		by_function.setdefault(row.parent, []).append(row)

	for function, group_rows in by_function.items():
		current = frappe.db.get_value("Function", function, ["group", "is_shared", "church"], as_dict=True)
		if current and not current.group and not current.is_shared:
			move_group_row(function, current.church or default_church(), group_rows)


def move_group_row(function: str, church: str | None, group_rows: list) -> None:
	moved = next((row for row in group_rows if is_group_of_church(row.association, church)), None)
	if not moved:
		return
	frappe.db.set_value("Function", function, "group", moved.association, update_modified=False)
	frappe.db.delete("Function Association", moved.name)

	kept = [row.association or "" for row in group_rows if row is not moved]
	if kept:
		frappe.get_doc("Function", function).add_comment(
			"Comment",
			_("Group {0} moved to the Group field. These Group associations stay: {1}.").format(
				moved.association, ", ".join(kept)
			),
		)


def is_group_of_church(group: str | None, church: str | None) -> bool:
	"""True when *group* exists and belongs to *church* or to no church, as validate_group allows."""
	group_church = frappe.db.get_value("Group", group, ["name", "church"], as_dict=True) if group else None
	return bool(group_church) and (not group_church.church or group_church.church == church)
