import frappe
from frappe import _
from pypika import Field, Order

from churchit.church_scope import scoped
from churchit.query import Greatest, Round
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Link", "label": _("Fund"), "options": "Fund", "width": 200},
		{"fieldname": "goal_amount", "fieldtype": "Currency", "label": _("Goal"), "width": 130},
		{"fieldname": "balance", "fieldtype": "Currency", "label": _("Balance"), "width": 130},
		{"fieldname": "remaining", "fieldtype": "Currency", "label": _("Remaining"), "width": 130},
		{"fieldname": "goal_progress", "fieldtype": "Percent", "label": _("Progress"), "width": 120},
	]


def get_data(filters=None):
	Fund = frappe.qb.DocType("Fund")

	query = (
		frappe.qb.from_(Fund)
		.select(
			Fund.name.as_("fund"),
			Fund.goal_amount,
			Fund.balance,
			Greatest(Fund.goal_amount - Fund.balance, 0).as_("remaining"),
			Round((Fund.balance / Fund.goal_amount) * 100, 1).as_("goal_progress"),
		)
		.where(Fund.goal_amount > 0)
		.orderby(Field("goal_progress"), order=Order.desc)
	)
	return scoped(query, Fund, filters).run(as_dict=True)
