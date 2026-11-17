import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce, Max
from frappe.utils import add_days, cint, getdate
from pypika import Case

from churchit.church_people.doctype.visitation_log.visitation_log import has_no_later_visit
from churchit.church_prayers.prayer_access import CLOSED_STATUSES
from churchit.church_scope import scoped
from churchit.contacts import get_primary_email, get_primary_phone
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "person", "fieldtype": "Link", "label": _("Person"), "options": "Person", "width": 240},
		{"fieldname": "reason", "fieldtype": "Data", "label": _("Reason"), "width": 200},
		{"fieldname": "last_event_date", "fieldtype": "Date", "label": _("Last Event"), "width": 110},
		{"fieldname": "primary_phone", "fieldtype": "Data", "label": _("Phone"), "width": 130},
		{"fieldname": "email", "fieldtype": "Data", "label": _("Email"), "width": 200},
	]


def get_data(filters=None):
	window_days = cint((filters or {}).get("window_days", 30)) or 30

	Visitation = frappe.qb.DocType("Visitation Log")
	Prayer = frappe.qb.DocType("Prayer Request")

	visits_query = (
		frappe.qb.from_(Visitation)
		.select(Visitation.person.as_("person"), Max(Visitation.visit_date).as_("last_event_date"))
		.where(
			(Visitation.visit_date >= add_days(getdate(), -window_days))
			& (Visitation.follow_up_needed == 1)
			& has_no_later_visit(Visitation)
		)
		.groupby(Visitation.person)
	)
	recent_visits = scoped(visits_query, Visitation, filters).run(as_dict=True)

	prayed_for = (
		Case()
		.when((Prayer.recipient_type == "Person") & Prayer.recipient.isnotnull(), Prayer.recipient)
		.else_(Prayer.requestor)
	)
	prayer_query = (
		frappe.qb.from_(Prayer)
		.select(prayed_for.as_("person"), Max(Prayer.creation).as_("last_event_date"))
		.where(
			Coalesce(Prayer.status, "").notin(list(CLOSED_STATUSES))
			& (Prayer.urgent == 1)
			& prayed_for.isnotnull()
		)
		.groupby(prayed_for)
	)
	active_prayer_persons = scoped(prayer_query, Prayer, filters).run(as_dict=True)

	rows = []
	for r in recent_visits:
		r["reason"] = _("Visitation follow-up needed")
		rows.append(r)
	for r in active_prayer_persons:
		r["reason"] = _("Urgent prayer request open")
		rows.append(r)

	for row in rows:
		person = row.get("person")
		row["primary_phone"] = get_primary_phone("Person", person)
		row["email"] = get_primary_email("Person", person)
	return rows
