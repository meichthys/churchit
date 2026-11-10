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
			"fieldname": "total_donations",
			"fieldtype": "Currency",
			"label": _("Total Donations"),
			"width": 140,
		},
		{
			"fieldname": "total_disbursed",
			"fieldtype": "Currency",
			"label": _("Total Disbursed"),
			"width": 140,
		},
		{
			"fieldname": "retained",
			"fieldtype": "Currency",
			"label": _("Retained"),
			"width": 140,
		},
		{
			"fieldname": "fiscal_year",
			"fieldtype": "Int",
			"label": _("Fiscal Year"),
			"width": 100,
		},
	]


def get_data(filters=None):
	year = (filters or {}).get("year") or frappe.utils.now_datetime().year
	year = int(year)

	Summary = frappe.qb.DocType("Missionary Support Summary")
	query = (
		frappe.qb.from_(Summary)
		.select(
			Summary.missionary,
			Summary.total_donations,
			Summary.total_disbursed,
			Summary.retained,
			Summary.year.as_("fiscal_year"),
		)
		.where(Summary.year == year)
	)

	query = scoped(query, Summary, filters)
	rows = query.run(as_dict=True)

	result = []
	for r in rows:
		result.append(
			{
				"missionary": r.missionary,
				"total_donations": frappe.utils.flt(r.total_donations),
				"total_disbursed": frappe.utils.flt(r.total_disbursed),
				"retained": frappe.utils.flt(r.retained),
				"fiscal_year": r.fiscal_year,
			}
		)

	return result
