import frappe

from churchit.query import CurDate, DayOfWeek, Month, Week
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 200},
		{"fieldname": "birthday", "fieldtype": "Date", "label": "Birthday", "width": 120},
	]


def get_data():
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")

	return (
		frappe.qb.from_(Person)
		.join(LifeEvent)
		.on(
			(LifeEvent.parent == Person.name)
			& (LifeEvent.parenttype == "Person")
			& (LifeEvent.event_type == "Birth")
		)
		.select(Person.name, LifeEvent.date.as_("birthday"))
		.where(
			LifeEvent.date.isnotnull()
			& (Week(LifeEvent.date, 1) == Week(CurDate(), 1))
			& (Month(LifeEvent.date) == Month(CurDate()))
		)
		.orderby(DayOfWeek(LifeEvent.date))
		.orderby(Person.full_name)
		.run(as_dict=True)
	)
