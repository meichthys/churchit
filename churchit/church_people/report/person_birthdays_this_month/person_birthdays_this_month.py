import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.contacts import primary_email_query, primary_phone_query
from churchit.query import CurDate, DayOfMonth, Month, Year
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{"fieldname": "birthday", "fieldtype": "Date", "label": _("Birthday"), "width": 120},
		{"fieldname": "age", "fieldtype": "Int", "label": _("Turning"), "width": 80},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": _("Phone"), "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Email"), "width": 200},
	]


def get_data(filters=None):
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	query = (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on(
			(LifeEvent.parent == Person.name)
			& (LifeEvent.parenttype == "Person")
			& (LifeEvent.event_type == "Birth")
		)
		.select(
			Person.name,
			LifeEvent.date.as_("birthday"),
			(Year(CurDate()) - Year(LifeEvent.date)).as_("age"),
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
		)
		.where(LifeEvent.date.isnotnull() & (Month(LifeEvent.date) == Month(CurDate())))
		.orderby(DayOfMonth(LifeEvent.date))
		.orderby(Person.full_name)
	)
	return scoped(query, Person, filters).run(as_dict=True)
