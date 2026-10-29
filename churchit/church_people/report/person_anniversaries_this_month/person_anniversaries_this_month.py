import frappe
from frappe import _

from churchit.church_people.doctype.family.family import primary_contacts
from churchit.church_people.membership import living_people_filter
from churchit.church_scope import scoped
from churchit.query import CurDate, DayOfMonth, Month
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 200},
		{"fieldname": "anniversary", "fieldtype": "Date", "label": _("Anniversary"), "width": 120},
		{"fieldname": "marriage_years", "fieldtype": "Int", "label": _("Years"), "width": 80},
		{"fieldname": "spouse", "fieldtype": "Link", "label": _("Spouse"), "options": "Person", "width": 200},
	]


def get_data(filters=None):
	Person = frappe.qb.DocType("Person")
	Spouse = frappe.qb.DocType("Person").as_("spouse")

	query = (
		frappe.qb.from_(Person)
		.left_join(Spouse)
		.on(Spouse.name == Person.spouse)
		.select(Person.name, Person.anniversary, Person.marriage_years, Person.spouse)
		.where(
			Person.anniversary.isnotnull()
			& (Month(Person.anniversary) == Month(CurDate()))
			& Person.name.isin(primary_contacts())
		)
		.where(living_people_filter(Person) & (Spouse.name.isnull() | living_people_filter(Spouse)))
		.orderby(DayOfMonth(Person.anniversary))
		.orderby(Person.full_name)
	)
	return scoped(query, Person, filters).run(as_dict=True)
