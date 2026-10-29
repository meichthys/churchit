# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.dashboard import count_people_in_list


@frappe.whitelist()
def get_count():
	return count_people_in_list("Inactivity Candidates")
