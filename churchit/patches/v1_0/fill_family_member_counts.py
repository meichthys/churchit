# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Store each family's member count for the first time, so the Family list and preview show it."""

import frappe
from frappe.query_builder.functions import Count


def execute():
	Members = frappe.qb.DocType("Family Members")
	counts = (
		frappe.qb.from_(Members)
		.select(Members.parent, Count(Members.name))
		.where(Members.parenttype == "Family")
		.groupby(Members.parent)
		.run()
	)
	for family, count in counts:
		frappe.db.set_value("Family", family, "member_count", count, update_modified=False)
