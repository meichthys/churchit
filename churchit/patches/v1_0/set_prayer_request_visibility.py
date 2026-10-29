# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Move Prayer Request's Is Private tick to Who Can See It: Private when ticked, else Whole Church.

Runs pre_model_sync and adds the visibility column itself. Model sync would add it with its default, Whole
Church, for every request, and a later patch failing would leave each private request on show until migrate
was repaired. Migrate keeps the old column after the field goes; the tick is cleared as it moves, so a
second run changes nothing.
"""

import frappe

from churchit.church_prayers.prayer_access import PRAYER_REQUEST, PRIVATE


def execute():
	if not frappe.db.has_column(PRAYER_REQUEST, "is_private"):
		return
	if not frappe.db.has_column(PRAYER_REQUEST, "visibility"):
		frappe.reload_doc("church_prayers", "doctype", "prayer_request", force=True)
	Request = frappe.qb.DocType(PRAYER_REQUEST)
	(
		frappe.qb.update(Request)
		.set(Request.visibility, PRIVATE)
		.set(Request.is_private, 0)
		.where(Request.is_private == 1)
		.run()
	)
