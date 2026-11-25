# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe

from churchit.contacts import NO_TEXT_PHONE_TYPES


def execute():
	"""Untick New Numbers Receive Texts on the default types that cannot text, and set every number from its type."""
	frappe.db.set_value("Phone Type", {"name": ("in", NO_TEXT_PHONE_TYPES)}, "receives_texts", 0)
	no_texts = frappe.get_all("Phone Type", filters={"receives_texts": 0}, pluck="name")

	number = frappe.qb.DocType("Phone Number")
	frappe.qb.update(number).set(number.receives_texts, 1).set(
		number.texts_from_type, number.phone_type
	).run()
	if no_texts:
		frappe.qb.update(number).set(number.receives_texts, 0).where(number.phone_type.isin(no_texts)).run()
