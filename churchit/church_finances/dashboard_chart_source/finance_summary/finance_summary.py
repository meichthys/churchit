import frappe
from frappe.query_builder.functions import Coalesce, Sum

from churchit.church_scope import scoped
from churchit.dashboard import bucket_label, time_buckets


@frappe.whitelist()
def get(
	chart_name: str | None = None,
	chart: str | dict | None = None,
	no_cache: bool | int | None = None,
	filters: str | list | dict | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	timespan: str | None = None,
	time_interval: str | None = None,
	**kwargs,
):
	frappe.has_permission("Collection", "report", throw=True)
	time_interval = time_interval or "Monthly"
	timespan = timespan or "Last Year"

	buckets = time_buckets(timespan, time_interval, from_date, to_date)
	labels = [bucket_label(start, time_interval) for start, _ in buckets]

	collections = [_sum_in_range("Collection", "date", "total_amount", s, e) for s, e in buckets]
	expenses = [_sum_in_range("Expense", "date", "amount", s, e) for s, e in buckets]

	return {
		"labels": labels,
		"datasets": [
			{"name": "Collections", "values": collections},
			{"name": "Expenses", "values": expenses},
		],
	}


def _sum_in_range(doctype, date_field, amount_field, start, end):
	table = frappe.qb.DocType(doctype)
	query = (
		frappe.qb.from_(table)
		.select(Coalesce(Sum(table[amount_field]), 0))
		.where((table.docstatus == 1) & table[date_field].between(start, end))
	)
	return float(scoped(query, table, {}).run()[0][0] or 0)
