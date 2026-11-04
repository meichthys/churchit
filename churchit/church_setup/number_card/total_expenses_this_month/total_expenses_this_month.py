# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.dashboard import total_of_saved_list


@frappe.whitelist()
def get_value():
	return total_of_saved_list("Expenses This Month", "Sum", "amount")
