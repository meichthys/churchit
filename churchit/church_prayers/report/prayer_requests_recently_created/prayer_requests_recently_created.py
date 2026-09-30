import frappe
from frappe import _

from churchit.church_scope import scoped
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{
			"fieldname": "status",
			"fieldtype": "Link",
			"label": _("Status"),
			"options": "Prayer Request Status",
			"width": 120,
		},
		{
			"fieldname": "type",
			"fieldtype": "Link",
			"label": _("Type"),
			"options": "Prayer Request Type",
			"width": 120,
		},
		{
			"fieldname": "recipient",
			"fieldtype": "Dynamic Link",
			"label": _("Recipient"),
			"options": "recipient_type",
			"width": 150,
		},
		{"fieldname": "details", "fieldtype": "Data", "label": _("Details"), "width": 300},
		{
			"fieldname": "name",
			"fieldtype": "Link",
			"label": _("Link to Request"),
			"options": "Prayer Request",
			"width": 150,
		},
	]


def get_data(filters):
	request_since = (filters or {}).get("request_since")

	Prayer = frappe.qb.DocType("Prayer Request")

	query = (
		frappe.qb.from_(Prayer)
		.select(
			Prayer.status,
			Prayer.type,
			Prayer.recipient_type,
			Prayer.recipient,
			Prayer.request.as_("details"),
			Prayer.name,
		)
		.where(Prayer.creation > request_since)
	)
	return scoped(query, Prayer, filters).run(as_dict=True)
