# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.model.document import Document


class PositionType(Document):
	pass


@frappe.whitelist()
def assign_position_to_person(position_type, person, start_date, end_date=None, notes=None):
	frappe.has_permission("Person", "write", throw=True)

	position_type_doc = frappe.get_doc("Position Type", position_type)
	if position_type_doc.is_single_person_role:
		active_holder = frappe.db.get_value(
			"Position",
			{"position": position_type, "end_date": ("is", "not set"), "parent": ("!=", person)},
			"parent",
		)
		if active_holder:
			holder_name = frappe.db.get_value("Person", active_holder, "full_name") or active_holder
			frappe.throw(
				frappe._("{0} is a single-person role currently held by {1}.").format(
					position_type, holder_name
				)
			)

	doc = frappe.get_doc("Person", person)
	doc.append(
		"positions",
		{
			"position": position_type,
			"start_date": start_date,
			"end_date": end_date or None,
			"notes": notes or "",
		},
	)
	doc.save()
	frappe.db.commit()
	return doc.name
