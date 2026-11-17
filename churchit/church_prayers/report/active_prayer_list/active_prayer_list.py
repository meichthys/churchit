import frappe
from frappe import _
from frappe.query_builder.functions import Coalesce
from frappe.utils import getdate, now_datetime
from pypika import Order

from churchit.church_prayers.prayer_access import CLOSED_STATUSES, PRAYER_TEAM, WHOLE_CHURCH
from churchit.church_scope import get_church_columns, scoped
from churchit.query import DateDiff
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = [*get_columns(), *get_church_columns(filters)]
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Request"),
			"options": "Prayer Request",
			"width": 300,
		},
		{"fieldname": "recipient_name", "fieldtype": "Data", "label": _("For"), "width": 160},
		{"fieldname": "request", "fieldtype": "Small Text", "label": _("Details"), "width": 320},
		{"fieldname": "visibility", "fieldtype": "Data", "label": _("Shared With"), "width": 110},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Prayer Request Type",
			"width": 130,
		},
		{"fieldname": "urgent", "fieldtype": "Check", "label": _("Urgent"), "width": 70},
		{
			"fieldname": "requestor",
			"fieldtype": "Link",
			"label": _("Requester"),
			"options": "Person",
			"width": 200,
		},
		{"fieldname": "days_open", "fieldtype": "Int", "label": _("Days Open"), "width": 100},
		{
			"fieldname": "status",
			"fieldtype": "Link",
			"label": _("Status"),
			"options": "Prayer Request Status",
			"width": 140,
		},
	]


def get_visibility_condition(Prayer, filters=None):
	"""The chosen visibility, else every request the whole church or the prayer team sees."""
	chosen = (filters or {}).get("visibility")
	if chosen:
		return Prayer.visibility == chosen
	return Prayer.visibility.isin([WHOLE_CHURCH, PRAYER_TEAM])


def get_data(filters=None):
	Prayer = frappe.qb.DocType("Prayer Request")

	query = (
		frappe.qb.from_(Prayer)
		.select(
			Prayer.name,
			Prayer.church,
			Prayer.recipient_name,
			Prayer.request,
			Prayer.visibility,
			Prayer.type,
			Prayer.urgent,
			Prayer.requestor,
			Prayer.status,
			DateDiff(getdate(), Prayer.creation).as_("days_open"),
		)
		.where(
			Coalesce(Prayer.status, "").notin(list(CLOSED_STATUSES))
			& (Prayer.end_date.isnull() | (Prayer.end_date >= now_datetime()))
			& get_visibility_condition(Prayer, filters)
		)
		.orderby(Prayer.urgent, order=Order.desc)
		.orderby(Prayer.creation, order=Order.desc)
	)
	return scoped(query, Prayer, filters).run(as_dict=True)
