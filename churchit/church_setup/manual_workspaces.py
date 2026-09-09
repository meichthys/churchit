import frappe

MANUAL_WORKSPACE_PREFIX = "Manual: "


def hide_manual_desktop_icons():
	"""Keep each module's Manual page reachable only from its own sidebar link.

	Frappe auto-creates a Desktop Icon for every public Workspace on install and
	migrate (frappe.desk.doctype.desktop_icon.create_desktop_icons_from_workspace),
	with no flag to opt a workspace out — it ignores parent_page entirely. Manual
	workspaces are meant to open only from the "Manual" link inside their own
	module's sidebar, so re-hide whatever Frappe (re)generated for them on every
	migrate instead of relying on a shipped-hidden fixture, which Frappe's own
	sync can silently replace.
	"""
	icons = frappe.get_all(
		"Desktop Icon",
		filters={"name": ("like", f"{MANUAL_WORKSPACE_PREFIX}%"), "hidden": 0},
		pluck="name",
	)
	for name in icons:
		frappe.db.set_value("Desktop Icon", name, "hidden", 1, update_modified=False)
