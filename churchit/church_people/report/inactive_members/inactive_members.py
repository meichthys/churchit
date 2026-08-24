import frappe
from frappe.query_builder.functions import Coalesce, Max
from frappe.utils import cint
from pypika import Field, Order

from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import CurDate, DateDiff
from churchit.utils import set_report_link_titles

ATTENDED_TYPES = ("Confirmed", "Checked-In", "Assumed")


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": "Member Since", "width": 120},
		{"fieldname": "last_attended", "fieldtype": "Date", "label": "Last Attended", "width": 120},
		{"fieldname": "days_absent", "fieldtype": "Int", "label": "Days Absent", "width": 100},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	threshold_days = cint((filters or {}).get("threshold_days", 60))

	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	def last_attended():
		return (
			frappe.qb.from_(Attendance)
			.join(Function)
			.on(Function.name == Attendance.parent)
			.select(Max(Function.start_date))
			.where((Attendance.person == Person.name) & Attendance.attendance_type.isin(list(ATTENDED_TYPES)))
		)

	def membership_date():
		return (
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
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			membership_date().as_("membership_date"),
			last_attended().as_("last_attended"),
			DateDiff(CurDate(), Coalesce(last_attended(), membership_date())).as_("days_absent"),
		)
		.where(Person.membership_status == "Active")
		.having((Field("days_absent") > threshold_days) | Field("last_attended").isnull())
		.orderby(Field("days_absent"), order=Order.desc)
		.run(as_dict=True)
	)
