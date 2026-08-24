import frappe
from frappe.utils import cint
from pypika import Field, Interval, Order

from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import CurDate
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": "Joined", "width": 110},
		{"fieldname": "membership_status", "fieldtype": "Link", "label": "Status", "options": "Member Status", "width": 110},
		{"fieldname": "family", "fieldtype": "Link", "label": "Family", "options": "Family", "width": 200},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	days = cint((filters or {}).get("days", 90)) or 90

	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	membership_date = (
		frappe.qb.from_(LifeEvent)
		.select(LifeEvent.date)
		.where((LifeEvent.parent == Person.name) & (LifeEvent.event_type == "Membership"))
		.orderby(LifeEvent.date)
		.limit(1)
	)

	return (
		frappe.qb.from_(Person)
		.select(
			Person.name,
			Person.membership_status,
			Person.family,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			membership_date.as_("membership_date"),
		)
		.where(Person.membership_status == "Active")
		.having(
			Field("membership_date").isnotnull()
			& (Field("membership_date") >= CurDate() - Interval(days=days))
		)
		.orderby(Field("membership_date"), order=Order.desc)
		.run(as_dict=True)
	)
