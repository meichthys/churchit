import frappe
from frappe import _

from churchit.church_people.celebrations import get_birthday_rows
from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.query import month_day_this_week, this_week
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
	]


def get_data(filters=None):
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(Person.name, Person.full_name, Person.birth_month, Person.birth_day, Person.birth_date)
		.where(month_day_this_week(Person.birth_month, Person.birth_day))
		.where(living_people_filter(Person))
	)
	return get_birthday_rows(scoped(query, Person, filters).run(as_dict=True), *this_week())
