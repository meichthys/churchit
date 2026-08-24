import frappe
from frappe.query_builder.functions import Sum

from churchit.utils import set_report_link_titles


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

	Donation = frappe.qb.DocType("Donation")
	Collection = frappe.qb.DocType("Collection")
	Expense = frappe.qb.DocType("Expense")

	income = {
		r["fund"]: r["total"]
		for r in (
			frappe.qb.from_(Donation)
			.join(Collection)
			.on(Collection.name == Donation.parent)
			.select(Donation.fund, Sum(Donation.amount).as_("total"))
			.where((Collection.docstatus == 1) & Collection.date[from_date:to_date])
			.groupby(Donation.fund)
			.run(as_dict=True)
		)
	}

	expenses = {
		r["fund"]: r["total"]
		for r in (
			frappe.qb.from_(Expense)
			.select(Expense.associated_fund.as_("fund"), Sum(Expense.amount).as_("total"))
			.where((Expense.docstatus == 1) & Expense.date[from_date:to_date])
			.groupby(Expense.associated_fund)
			.run(as_dict=True)
		)
	}

	funds = sorted(set(income) | set(expenses))
	rows = []
	for f in funds:
		inc = income.get(f, 0) or 0
		exp = expenses.get(f, 0) or 0
		rows.append({"fund": f, "income": inc, "expense": exp, "net": inc - exp})
	return rows
