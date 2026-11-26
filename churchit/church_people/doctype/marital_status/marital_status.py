# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.model.document import Document

MARRIED = "Married"
WIDOWED = "Widowed"
DEFAULT_STATUSES = {
	"Single": "Has never been married.",
	MARRIED: "Married now.",
	WIDOWED: "The spouse has died. The spouse and anniversary stay on the record.",
	"Divorced": "The marriage ended in divorce.",
}
# The statuses that have a spouse and an anniversary
WITH_SPOUSE = (MARRIED, WIDOWED)


class MaritalStatus(Document):
	pass
