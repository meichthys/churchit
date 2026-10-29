import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, getdate

from churchit.church_people.celebrations import get_birthday_rows
from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.contacts import primary_email_query, primary_phone_query
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
	today = getdate()
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(
			Person.name,
			Person.full_name,
			Person.birth_month,
			Person.birth_day,
			Person.birth_date,
			primary_phone_query(Person).as_("primary_phone"),
			primary_email_query(Person).as_("email"),
		)
		.where(Person.birth_month == today.month)
		.where(living_people_filter(Person))
	)
	people = scoped(query, Person, filters).run(as_dict=True)
	return get_birthday_rows(people, get_first_day(today), get_last_day(today))
