# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The people whose personal data the daily job removes by a date, as People Settings sets the years."""

import frappe
from frappe import _
from frappe.utils import add_days, add_years, today

from churchit.church_people.privacy import get_due_query, get_retention_years
from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	filters = frappe._dict(filters or {})
	years = get_retention_years()
	if not years:
		return get_columns(), [], _("Personal data is never removed. Set the years in People Settings.")
	columns = get_columns()
	data = get_data(filters, years)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "removal_date", "fieldtype": "Date", "label": _("Removal Date"), "width": 120},
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 220},
		{"fieldname": "inactive_since", "fieldtype": "Date", "label": _("Inactive Since"), "width": 120},
		{
			"fieldname": "inactive_reason",
			"fieldtype": "Link",
			"label": _("Inactive Reason"),
			"options": "Inactive Reason",
			"width": 160,
		},
	]


def get_data(filters, years: int) -> list[dict]:
	"""The people due by the Due By date, the first to go first. Those already due go on the next daily run."""
	Person = frappe.qb.DocType("Person")
	due_by = filters.due_by or add_days(today(), 30)
	query = get_due_query(Person, add_years(due_by, -years)).select(
		Person.name.as_("person"), Person.inactive_since, Person.inactive_reason
	)
	rows = scoped(query, Person, filters).run(as_dict=True)
	for row in rows:
		row.removal_date = add_years(row.inactive_since, years)
	return rows
