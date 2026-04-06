import frappe


def execute():
	"""Remove colon from prayer request report names to fix module resolution."""
	renames = {
		"Prayer Requests: Recently Created": "Prayer Requests Recently Created",
		"Prayer Requests: Recently Answered": "Prayer Requests Recently Answered",
	}

	for old_name, new_name in renames.items():
		if frappe.db.exists("Report", old_name) and not frappe.db.exists("Report", new_name):
			frappe.rename_doc("Report", old_name, new_name, force=True)
