import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.query import DayOfWeek, falls_this_week
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
		.select(Person.name, LifeEvent.date.as_("birthday"))
		.where(LifeEvent.date.isnotnull() & falls_this_week(LifeEvent.date))
		.orderby(DayOfWeek(LifeEvent.date))
		.orderby(Person.full_name)
	)
	return scoped(query, Person, filters).run(as_dict=True)
