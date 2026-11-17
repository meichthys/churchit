import frappe
from frappe import _
from frappe.query_builder.functions import Max
from frappe.utils import cint, getdate
from pypika import Field, Order

from churchit.church_ministries.attendance import COUNTED_TYPES
from churchit.church_people.membership import is_active_member
from churchit.church_scope import get_church_columns, scoped
from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import DateDiff
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": _("Member Since"), "width": 120},
		{"fieldname": "last_attended", "fieldtype": "Date", "label": _("Last Attended"), "width": 120},
		{"fieldname": "days_absent", "fieldtype": "Int", "label": _("Days Absent"), "width": 100},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": _("Phone"), "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Email"), "width": 200},
	]


def get_data(filters=None):
	threshold_days = cint((filters or {}).get("threshold_days", 60))
	today = getdate()

	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")
	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	# One grouped pass over the attendance rows, joined once, instead of a subquery for each person.
	attended = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Function.name == Attendance.parent)
		.select(Attendance.person, Max(Function.start_date).as_("last_attended"))
		.where(Attendance.attendance_type.isin(COUNTED_TYPES) & (Function.start_date <= today))
		.where(Function.auto_repeat == 0)
		.groupby(Attendance.person)
	).as_("attended")

	membership_date = (
		frappe.qb.from_(LifeEvent)
		.select(LifeEvent.date)
		.where((LifeEvent.parent == Person.name) & (LifeEvent.event_type == "Membership"))
		.orderby(LifeEvent.date)
		.limit(1)
	)

	query = (
		frappe.qb.from_(Person)
		.left_join(attended)
		.on(attended.person == Person.name)
		.select(
			Person.name,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
			membership_date.as_("membership_date"),
			attended.last_attended,
			DateDiff(today, attended.last_attended).as_("days_absent"),
			Person.church,
		)
		.where(is_active_member(Person))
		.having((Field("days_absent") > threshold_days) | Field("last_attended").isnull())
		.orderby(Field("last_attended").isnull(), order=Order.desc)
		.orderby(Field("days_absent"), order=Order.desc)
	)
	return scoped(query, Person, filters).run(as_dict=True)
