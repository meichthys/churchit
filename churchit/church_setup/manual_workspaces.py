# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Hide Manual workspaces from the desk dashboard on every migrate."""

import frappe

MANUAL_PREFIX = "Manual: "


def hide_manual_workspaces() -> None:
	"""Set is_hidden on every Workspace whose name starts with 'Manual: '.

	Frappe re-imports standard Workspace records on each migrate and resets
	is_hidden to whatever the JSON says. Running this after migrate keeps
	manual workspaces off the dashboard without touching each JSON file.
	"""
	names = frappe.get_all("Workspace", filters={"name": ["like", f"{MANUAL_PREFIX}%"]}, pluck="name")
	for name in names:
		frappe.db.set_value("Workspace", name, "is_hidden", 1)
