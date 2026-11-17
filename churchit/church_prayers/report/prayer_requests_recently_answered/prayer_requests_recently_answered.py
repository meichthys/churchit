import frappe
from frappe import _
from pypika import Order

from churchit.church_scope import get_church_columns, scoped
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
			"width": 240,
		},
		{"fieldname": "answered_on", "fieldtype": "Date", "label": _("Answered On"), "width": 120},
		{"fieldname": "recipient_name", "fieldtype": "Data", "label": _("Prayer For"), "width": 160},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Prayer Request Type",
			"width": 120,
		},
		{"fieldname": "details", "fieldtype": "Data", "label": _("Details"), "width": 300},
	]


def get_data(filters):
	"""The requests answered on or after the Answered Since date, the latest first."""
	answered_since = (filters or {}).get("request_since")

	Prayer = frappe.qb.DocType("Prayer Request")

	query = (
		frappe.qb.from_(Prayer)
		.select(
			Prayer.name,
			Prayer.church,
			Prayer.answered_on,
			Prayer.recipient_name,
			Prayer.type,
			Prayer.request.as_("details"),
		)
		.where((Prayer.status == "Answered") & (Prayer.answered_on >= answered_since))
		.orderby(Prayer.answered_on, order=Order.desc)
		.orderby(Prayer.name, order=Order.desc)
	)
	return scoped(query, Prayer, filters).run(as_dict=True)
