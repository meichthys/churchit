# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe


@frappe.whitelist()
def get_count():
	"""Comments on the prayer requests the reader may see.

	A Document Type card on Comment counted every church's, and threw
	`Insufficient Permission for Comment` for a Church Manager, who has no read
	on Comment at all. Comment carries no church of its own, so the count is
	anchored to the requests `get_list` gives the reader: their church's, and
	only their own when their role reads only its own.
	"""
	requests = frappe.get_list("Prayer Request", pluck="name")
	if not requests:
		return 0
	return frappe.db.count(
		"Comment",
		{
			"comment_type": "Comment",
			"reference_doctype": "Prayer Request",
			"reference_name": ("in", requests),
		},
	)
