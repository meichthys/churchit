# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Send New Care Request only for a request that no caregiver gets on their To Do list.

The caregiver's assignment already emails them. A condition that a church set stays as it is.
"""

import frappe

from churchit.church_people.doctype.care_request.care_request import CARE_CONDITION, CARE_NOTIFICATION


def execute():
	if frappe.db.get_value(
		"Notification", {"name": CARE_NOTIFICATION, "is_standard": 0, "condition": ("is", "not set")}
	):
		frappe.db.set_value(
			"Notification", CARE_NOTIFICATION, {"condition": CARE_CONDITION, "condition_type": "Python"}
		)
