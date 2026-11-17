import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate
from pypika import Field, Order

from churchit.church_people.membership import is_active_member
from churchit.church_scope import get_church_columns, scoped
from churchit.contacts import primary_email_query, primary_phone_query
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "name", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "membership_date", "fieldtype": "Date", "label": _("Joined"), "width": 110},
		{
			"fieldname": "membership_status",
			"fieldtype": "Link",
			"label": _("Status"),
			"options": "Member Status",
			"width": 110,
		},
		{"fieldname": "family", "fieldtype": "Link", "label": _("Family"), "options": "Family", "width": 200},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": _("Phone"), "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Email"), "width": 200},
	]


def get_data(filters=None):
	days = cint((filters or {}).get("days", 90)) or 90
	Person = frappe.qb.DocType("Person")
	query = new_members_query(Person, days).select(
		Person.church,
		Person.membership_status,
		Person.family,
		primary_phone_query(Person).as_("primary_phone"),
		primary_email_query(Person).as_("email"),
	)
	return scoped(query, Person, filters).run(as_dict=True)


def new_members_query(Person, days: int):
	"""Active members whose first Membership event falls in the last *days* days, up to today.

	The New Members (30 days) card counts these rows, so the card and this report agree.
	"""
	LifeEvent = frappe.qb.DocType("Life Event")
	membership_date = (
		frappe.qb.from_(LifeEvent)
		.select(LifeEvent.date)
		.where((LifeEvent.parent == Person.name) & (LifeEvent.event_type == "Membership"))
		.orderby(LifeEvent.date)
		.limit(1)
	)
	today = getdate()
	return (
		frappe.qb.from_(Person)
		.select(Person.name, membership_date.as_("membership_date"))
		.where(is_active_member(Person))
		.having(Field("membership_date")[add_days(today, -days) : today])
		.orderby(Field("membership_date"), order=Order.desc)
	)
