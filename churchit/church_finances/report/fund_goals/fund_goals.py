import frappe
from pypika import Field, Order

from churchit.query import Greatest, Round
from churchit.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 200},
		{"fieldname": "goal_amount", "fieldtype": "Currency", "label": "Goal", "width": 130},
		{"fieldname": "balance", "fieldtype": "Currency", "label": "Balance", "width": 130},
		{"fieldname": "remaining", "fieldtype": "Currency", "label": "Remaining", "width": 130},
		{"fieldname": "goal_progress", "fieldtype": "Percent", "label": "Progress", "width": 120},
	]


def get_data():
	Fund = frappe.qb.DocType("Fund")

	return (
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
		.run(as_dict=True)
	)
