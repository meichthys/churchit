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
			"fieldname": "missionary",
			"fieldtype": "Link",
			"label": _("Missionary"),
			"options": "Missionary",
			"width": 180,
		},
		{
			"fieldname": "total_committed",
			"fieldtype": "Currency",
			"label": _("Total Committed"),
			"width": 130,
		},
		{
			"fieldname": "total_disbursed",
			"fieldtype": "Currency",
			"label": _("Total Disbursed"),
			"width": 130,
		},
		{
			"fieldname": "variance",
			"fieldtype": "Currency",
			"label": _("Variance"),
			"width": 130,
		},
		{
			"fieldname": "variance_pct",
			"fieldtype": "Percent",
			"label": _("Variance %"),
			"width": 100,
		},
		{
			"fieldname": "start_date",
			"fieldtype": "Date",
			"label": _("Start Date"),
			"width": 110,
		},
		{
			"fieldname": "end_date",
			"fieldtype": "Date",
			"label": _("End Date"),
			"width": 110,
		},
		{
			"fieldname": "variance_flagged",
			"fieldtype": "Check",
			"label": _("Flagged"),
			"width": 80,
		},
	]


def get_data(filters=None):
	Schedule = frappe.qb.DocType("Missionary Support Schedule")
	query = (
		frappe.qb.from_(Schedule)
		.select(
			Schedule.missionary,
			Schedule.total_committed,
			Schedule.total_disbursed,
			Schedule.variance,
			Schedule.variance_threshold,
			Schedule.variance_flagged,
			Schedule.start_date,
			Schedule.end_date,
		)
		.where(Schedule.status == "Active")
	)

	query = scoped(query, Schedule, filters)
	rows = query.run(as_dict=True)

	result = []
	for r in rows:
		committed = frappe.utils.flt(r.total_committed)
		variance = frappe.utils.flt(r.variance)
		pct = (abs(variance) / committed * 100) if committed > 0 else 0

		result.append({
			"missionary": r.missionary,
			"total_committed": committed,
			"total_disbursed": frappe.utils.flt(r.total_disbursed),
			"variance": variance,
			"variance_pct": pct,
			"start_date": r.start_date,
			"end_date": r.end_date,
			"variance_flagged": r.variance_flagged,
		})

	return result
