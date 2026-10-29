# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Count the Prayers recorded for each Prayer Request before the request stored its count."""

import frappe

from churchit.church_prayers.doctype.prayer.prayer import recount_prayers


def execute():
	requests = frappe.get_all(
		"Prayer Topic",
		filters={"parenttype": "Prayer", "topic_type": "Prayer Request"},
		pluck="topic",
		distinct=True,
	)
	recount_prayers(set(requests))
