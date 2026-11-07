# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.dashboard import count_people_in_list


@frappe.whitelist(methods=["GET", "POST"])
def get_count() -> dict:
	"""Number card: the people on the First-Time Visitors smart list in the caller's churches. Reads only."""
	return count_people_in_list("First-Time Visitors")
