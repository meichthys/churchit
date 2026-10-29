# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Booking"),
			"options": "Room Booking",
			"width": 120,
		},
		{
			"fieldname": "asset",
			"fieldtype": "Link",
			"label": _("Asset"),
			"options": "Church Asset",
			"width": 180,
		},
		{"fieldname": "purpose", "fieldtype": "Data", "label": _("Purpose"), "width": 180},
		{
			"fieldname": "requester",
			"fieldtype": "Link",
			"label": _("Requester"),
			"options": "Person",
			"width": 160,
		},
		{"fieldname": "checked_out_on", "fieldtype": "Datetime", "label": _("Checked Out On"), "width": 160},
		{"fieldname": "end_datetime", "fieldtype": "Datetime", "label": _("Due Back"), "width": 160},
	]


def get_data(filters) -> list[dict]:
	"""One row for each asset of a booking that is checked out and not returned, the most overdue first."""
	Booking = frappe.qb.DocType("Room Booking")
	BookingAsset = frappe.qb.DocType("Room Booking Asset")
	query = (
		frappe.qb.from_(Booking)
		.join(BookingAsset)
		.on((BookingAsset.parent == Booking.name) & (BookingAsset.parenttype == "Room Booking"))
		.select(
			Booking.name,
			BookingAsset.asset,
			Booking.purpose,
			Booking.requester,
			Booking.checked_out_on,
			Booking.end_datetime,
		)
		.where(Booking.checked_out_on.isnotnull() & Booking.returned_on.isnull())
		.orderby(Booking.end_datetime)
		.orderby(Booking.name)
		.orderby(BookingAsset.idx)
	)
	return scoped(query, Booking, filters).run(as_dict=True)
