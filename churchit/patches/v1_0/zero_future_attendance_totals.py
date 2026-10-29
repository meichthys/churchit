# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Set the attendance total of every Function dated in the future to 0.

A roster made ahead of a Function counted as attendance. A total now counts only once the Function
starts, and the daily `refresh_started_totals` job counts it then.
"""

import frappe
from frappe.utils import today


def execute():
	Function = frappe.qb.DocType("Function")
	(
		frappe.qb.update(Function)
		.set(Function.attendance_total, 0)
		.where((Function.start_date > today()) & (Function.attendance_total != 0))
		.run()
	)
