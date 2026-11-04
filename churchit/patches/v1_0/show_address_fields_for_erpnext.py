# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Remove the setters that hid Address fields ERPNext needs.

The Address customization now hides them only on sites without ERPNext, and sync never deletes a setter.
"""

import frappe

HIDDEN_FIELDS = (
	"email_id",
	"phone",
	"fax",
	"is_primary_address",
	"is_shipping_address",
	"disabled",
	"is_your_company_address",
)


def execute():
	frappe.db.delete(
		"Property Setter",
		{"doc_type": "Address", "property": "hidden", "field_name": ("in", HIDDEN_FIELDS), "value": "1"},
	)
