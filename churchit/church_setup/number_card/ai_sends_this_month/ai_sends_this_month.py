# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.dashboard import total_of_saved_list


@frappe.whitelist(methods=["GET", "POST"])
def get_value() -> dict:
	"""Number card: this month's records that churchit's own AI features sent to a model, from the Access Log. Reads only.

	Access Log is for System Managers, so anyone else gets a permission error.
	"""
	return total_of_saved_list("AI Sends")
