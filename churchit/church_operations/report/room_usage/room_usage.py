# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.query_builder.functions import GroupConcat
from frappe.utils import add_days, flt, time_diff_in_hours

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.room:
		frappe.has_permission("Room", doc=filters.room, throw=True)

	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"fieldname": "booking",
			"fieldtype": "Link",
			"label": _("Booking"),
			"options": "Room Booking",
			"width": 110,
		},
		{"fieldname": "room", "fieldtype": "Link", "label": _("Room"), "options": "Room", "width": 180},
		{"fieldname": "assets", "fieldtype": "Data", "label": _("Equipment"), "width": 200},
		{"fieldname": "start_datetime", "fieldtype": "Datetime", "label": _("Start"), "width": 160},
		{"fieldname": "end_datetime", "fieldtype": "Datetime", "label": _("End"), "width": 160},
		{"fieldname": "hours", "fieldtype": "Float", "label": _("Hours"), "precision": 2, "width": 80},
		{"fieldname": "status", "fieldtype": "Data", "label": _("Status"), "width": 100},
		{
			"fieldname": "requester",
			"fieldtype": "Link",
			"label": _("Requester"),
			"options": "Person",
			"width": 180,
		},
		{"fieldname": "purpose", "fieldtype": "Data", "label": _("Purpose"), "width": 220},
	]


def get_data(filters) -> list[dict]:
	"""One row for each booking the reader may see whose times overlap the dates."""
	Booking = frappe.qb.DocType("Room Booking")
	BookingAsset = frappe.qb.DocType("Room Booking Asset")
	Asset = frappe.qb.DocType("Church Asset")
	query = (
		frappe.qb.from_(Booking)
		.left_join(BookingAsset)
		.on((BookingAsset.parent == Booking.name) & (BookingAsset.parenttype == "Room Booking"))
		.left_join(Asset)
		.on(Asset.name == BookingAsset.asset)
		.select(
			Booking.name.as_("booking"),
			Booking.room,
			GroupConcat(Asset.title).separator(", ").as_("assets"),
			Booking.start_datetime,
			Booking.end_datetime,
			Booking.status,
			Booking.requester,
			Booking.purpose,
		)
		.groupby(Booking.name)
		.orderby(Booking.start_datetime)
		.orderby(Booking.room)
	)
	if filters.from_date:
		query = query.where(Booking.end_datetime > filters.from_date)
	if filters.to_date:
		query = query.where(Booking.start_datetime < add_days(filters.to_date, 1))
	if filters.room:
		query = query.where(Booking.room == filters.room)
	if filters.status:
		query = query.where(Booking.status == filters.status)

	rows = scoped(query, Booking, filters).run(as_dict=True)
	for row in rows:
		row.hours = flt(time_diff_in_hours(row.end_datetime, row.start_datetime), 2)
	return rows
