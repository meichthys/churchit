import frappe

from church.utils import set_report_link_titles


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	set_report_link_titles(columns, data)
	return columns, data


def get_columns():
	return [
		{"fieldname": "fund", "fieldtype": "Link", "label": "Fund", "options": "Fund", "width": 220},
		{"fieldname": "income", "fieldtype": "Currency", "label": "Income", "width": 140},
		{"fieldname": "expense", "fieldtype": "Currency", "label": "Expense", "width": 140},
		{"fieldname": "net", "fieldtype": "Currency", "label": "Net", "width": 140},
	]


def get_data(filters=None):
	from_date = (filters or {}).get("from_date") or frappe.utils.add_months(frappe.utils.nowdate(), -12)
	to_date = (filters or {}).get("to_date") or frappe.utils.nowdate()

	income = {
		r["fund"]: r["total"]
		for r in frappe.db.sql(
			"""
			SELECT d.fund, SUM(d.amount) AS total
			FROM `tabDonation` d
			JOIN `tabCollection` c ON c.name = d.parent
			WHERE c.docstatus = 1
				AND c.date BETWEEN %s AND %s
			GROUP BY d.fund
			""",
			(from_date, to_date),
			as_dict=True,
		)
	}

	expenses = {
		r["fund"]: r["total"]
		for r in frappe.db.sql(
			"""
			SELECT associated_fund AS fund, SUM(amount) AS total
			FROM `tabExpense`
			WHERE docstatus = 1
				AND date BETWEEN %s AND %s
			GROUP BY associated_fund
			""",
			(from_date, to_date),
			as_dict=True,
		)
	}

	funds = sorted(set(income) | set(expenses))
	rows = []
	for f in funds:
		inc = income.get(f, 0) or 0
		exp = expenses.get(f, 0) or 0
		rows.append({"fund": f, "income": inc, "expense": exp, "net": inc - exp})
	return rows
