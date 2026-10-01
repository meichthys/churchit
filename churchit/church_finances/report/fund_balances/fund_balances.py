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
		{"fieldname": "fund", "fieldtype": "Data", "label": _("Fund"), "width": 200},
		{"fieldname": "balance", "fieldtype": "Currency", "label": _("Balance"), "width": 150},
	]


def get_data(filters=None):
	Fund = frappe.qb.DocType("Fund")
	query = frappe.qb.from_(Fund).select(Fund.fund, Fund.balance)
	return scoped(query, Fund, filters).run(as_dict=True)
