# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document

CHILD_SAFETY_TRAINING = "Child Safety Training"

# The types a church starts with, and how many years a cleared one stays valid.
DEFAULT_TYPES = {
	"Criminal Background": 3,
	"Sex Offender Registry": 3,
	"Child Abuse Clearance": 5,
	"Driving Record": 3,
	CHILD_SAFETY_TRAINING: 2,
}
DESCRIPTIONS = {
	CHILD_SAFETY_TRAINING: "A course in keeping children and youth safe, for everyone who serves them. "
	"Record it as Cleared when the person completes the course.",
}


class BackgroundCheckType(Document):
	"""A kind of check or training a Person can hold, and how long a cleared one stays valid."""


def create_background_check_types():
	"""Make the standard check types that are missing; a type a church changed or removed stays as it is."""
	for check_type, valid_for_years in DEFAULT_TYPES.items():
		if not frappe.db.exists("Background Check Type", check_type):
			frappe.get_doc(
				{
					"doctype": "Background Check Type",
					"type": check_type,
					"valid_for_years": valid_for_years,
					"description": DESCRIPTIONS.get(check_type),
				}
			).insert(ignore_permissions=True)
