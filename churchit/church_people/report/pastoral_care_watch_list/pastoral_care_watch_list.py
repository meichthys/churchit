import frappe
from frappe.query_builder.functions import Coalesce, Max
from frappe.utils import cint
from pypika import Interval

from churchit.contacts import get_primary_email, get_primary_phone
from churchit.query import CurDate
from churchit.utils import set_report_link_titles

CLOSED_PRAYER_STATUSES = ("Answered", "Archived", "Closed")


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": "Person", "options": "Person", "width": 240},
		{"fieldname": "reason", "fieldtype": "Data", "label": "Reason", "width": 200},
		{"fieldname": "last_event_date", "fieldtype": "Date", "label": "Last Event", "width": 110},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": "Phone", "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": "Email", "width": 200},
	]


def get_data(filters=None):
	window_days = cint((filters or {}).get("window_days", 30)) or 30

	Visitation = frappe.qb.DocType("Visitation Log")
	Prayer = frappe.qb.DocType("Prayer Request")

	recent_visits = (
		frappe.qb.from_(Visitation)
		.select(Visitation.person.as_("person"), Max(Visitation.visit_date).as_("last_event_date"))
		.where(
			(Visitation.visit_date >= CurDate() - Interval(days=window_days))
			& (Visitation.follow_up_needed == 1)
		)
		.groupby(Visitation.person)
		.run(as_dict=True)
	)

	active_prayer_persons = (
		frappe.qb.from_(Prayer)
		.select(Prayer.requestor.as_("person"), Max(Prayer.creation).as_("last_event_date"))
		.where(
			Coalesce(Prayer.status, "").notin(list(CLOSED_PRAYER_STATUSES))
			& (Prayer.urgent == 1)
			& Prayer.requestor.isnotnull()
		)
		.groupby(Prayer.requestor)
		.run(as_dict=True)
	)

	rows = []
	for r in recent_visits:
		r["reason"] = "Visitation follow-up needed"
		rows.append(r)
	for r in active_prayer_persons:
		r["reason"] = "Urgent prayer request open"
		rows.append(r)

	for row in rows:
		person = row.get("person")
		row["primary_phone"] = get_primary_phone("Person", person)
		row["email"] = get_primary_email("Person", person)
	return rows
