# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Fill Answered On on each answered Prayer Request from the day it was last modified."""

import frappe

from churchit.query import Date


def execute():
	Prayer = frappe.qb.DocType("Prayer Request")
	(
		frappe.qb.update(Prayer)
		.set(Prayer.answered_on, Date(Prayer.modified))
		.where((Prayer.status == "Answered") & Prayer.answered_on.isnull())
		.run()
	)
