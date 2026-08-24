import frappe
from frappe.query_builder.functions import Coalesce
from pypika import Order

from churchit.query import CurDate, DateDiff
from churchit.utils import set_report_link_titles

CLOSED_STATUSES = ("Answered", "Archived", "Closed")


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Request", "options": "Prayer Request", "width": 180},
		{"fieldname": "title", "fieldtype": "Data", "label": "Title", "width": 240},
		{"fieldname": "type", "fieldtype": "Link", "label": "Type", "options": "Prayer Request Type", "width": 130},
		{"fieldname": "urgent", "fieldtype": "Check", "label": "Urgent", "width": 70},
		{"fieldname": "requestor", "fieldtype": "Link", "label": "Requestor", "options": "Person", "width": 200},
		{"fieldname": "days_open", "fieldtype": "Int", "label": "Days Open", "width": 100},
		{"fieldname": "status", "fieldtype": "Link", "label": "Status", "options": "Prayer Request Status", "width": 140},
	]


def get_data(filters=None):
	Prayer = frappe.qb.DocType("Prayer Request")

	return (
		frappe.qb.from_(Prayer)
		.select(
			Prayer.name,
			Prayer.title,
			Prayer.type,
			Prayer.urgent,
			Prayer.requestor,
			Prayer.status,
			DateDiff(CurDate(), Prayer.creation).as_("days_open"),
		)
		.where(Coalesce(Prayer.status, "").notin(list(CLOSED_STATUSES)))
		.orderby(Prayer.urgent, order=Order.desc)
		.orderby(Prayer.creation, order=Order.desc)
		.run(as_dict=True)
	)
