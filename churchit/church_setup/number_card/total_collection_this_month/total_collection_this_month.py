# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.dashboard import total_of_saved_list


@frappe.whitelist(methods=["GET", "POST"])
def get_value() -> dict:
	"""Number card: the total of this month's collections that the reader may see. Reads only."""
	return total_of_saved_list("Collections This Month", "Sum", "total_amount")
