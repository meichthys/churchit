# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.church_prayers.prayer_access import get_active_request_filters

REPORT = "Active Prayer Requests"


@frappe.whitelist(methods=["GET", "POST"])
def get_value() -> dict:
	"""Number card: the active prayer requests the reader may read, past End Dates left out. Reads only.

	`get_list` applies the reader's rights, church and Visibility. The Active Prayer Requests list cannot
	leave out ended requests (a saved list has no 'or' filter), so the card counts them itself and opens it.
	"""
	filters, or_filters = get_active_request_filters()
	count = frappe.get_list(
		"Prayer Request",
		fields=[{"COUNT": "*", "as": "result"}],
		filters=filters,
		or_filters=or_filters,
		order_by=None,
	)
	total = {"value": count[0]["result"] if count else 0, "fieldtype": "Int"}
	if frappe.get_cached_doc("Report", REPORT).is_permitted():
		total["route"] = ["List", "Prayer Request", "Report", REPORT]
	return total
