# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import add_days, today

from churchit.church_people.membership import TRACKED_FIELDS
from churchit.church_scope import scoped
from churchit.query import Date
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "date", "fieldtype": "Date", "label": _("Date"), "width": 110},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "field", "fieldtype": "Data", "label": _("Field"), "width": 120},
		{"fieldname": "previous_value", "fieldtype": "Data", "label": _("Previous Value"), "width": 150},
		{"fieldname": "value", "fieldtype": "Data", "label": _("New Value"), "width": 150},
	]


def get_data(filters):
	"""One row per change of a person's Membership or Status in the date range, newest first."""
	from_date = filters.from_date or add_days(today(), -90)
	to_date = filters.to_date or today()
	Milestone = frappe.qb.DocType("Milestone")
	Earlier = frappe.qb.DocType("Milestone").as_("earlier")
	Person = frappe.qb.DocType("Person")
	previous_value = (
		frappe.qb.from_(Earlier)
		.select(Earlier.value)
		.where(
			(Earlier.reference_type == "Person")
			& (Earlier.reference_name == Milestone.reference_name)
			& (Earlier.track_field == Milestone.track_field)
			& (Earlier.creation < Milestone.creation)
		)
		.orderby(Earlier.creation, order=Order.desc)
		.limit(1)
	)
	query = (
		frappe.qb.from_(Milestone)
		.join(Person)
		.on(Person.name == Milestone.reference_name)
		.select(
			Date(Milestone.creation).as_("date"),
			Person.name.as_("person"),
			Milestone.track_field.as_("field"),
			previous_value.as_("previous_value"),
			Milestone.value,
		)
		.where(
			(Milestone.reference_type == "Person")
			& Milestone.track_field.isin([filters.field] if filters.field else TRACKED_FIELDS)
			& Date(Milestone.creation)[from_date:to_date]
		)
		.orderby(Milestone.creation, order=Order.desc)
	)
	if filters.value:
		query = query.where(Milestone.value == filters.value)
	rows = scoped(query, Person, filters).run(as_dict=True)

	meta = frappe.get_meta("Person")
	for row in rows:
		row.field = _(meta.get_label(row.field))
	return rows
