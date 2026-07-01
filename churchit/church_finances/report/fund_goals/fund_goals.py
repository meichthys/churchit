import frappe

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
	return frappe.db.sql(
		"""
		SELECT
			name AS fund,
			goal_amount,
			balance,
			GREATEST(goal_amount - balance, 0) AS remaining,
			ROUND((balance / goal_amount) * 100, 1) AS goal_progress
		FROM `tabFund`
		WHERE goal_amount > 0
		ORDER BY goal_progress DESC
		""",
		as_dict=True,
	)
