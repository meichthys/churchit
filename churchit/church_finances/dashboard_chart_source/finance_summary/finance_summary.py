from bisect import bisect_right

import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import add_days

from churchit.church_scope import scoped
from churchit.dashboard import bucket_label, time_buckets
from churchit.query import Date


@frappe.whitelist(methods=["GET", "POST"])
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
) -> dict:
	"""Chart source: collections beside expenses for each period of the timespan, in the reader's churches. Reads only."""
	frappe.has_permission("Collection", "report", throw=True)
	time_interval = time_interval or "Monthly"
	timespan = timespan or "Last Year"

	buckets = time_buckets(timespan, time_interval, from_date, to_date)
	labels = [bucket_label(start, time_interval) for start, _ in buckets]

	collections = get_bucket_totals("Collection", "total_amount", buckets)
	expenses = get_bucket_totals("Expense", "amount", buckets)

	return {
		"labels": labels,
		"datasets": [
			{"name": "Collections", "values": collections},
			{"name": "Expenses", "values": expenses},
		],
	}


def get_bucket_totals(doctype: str, amount_field: str, buckets: list[tuple]) -> list[float]:
	"""The submitted amount in each of the back-to-back *buckets*, from one query grouped by day."""
	if not buckets:
		return []

	table = frappe.qb.DocType(doctype)
	day = Date(table.date)
	query = (
		frappe.qb.from_(table)
		.select(day, Sum(table[amount_field]))
		.where(
			(table.docstatus == 1)
			& (table.date >= buckets[0][0])
			& (table.date < add_days(buckets[-1][1], 1))
		)
		.groupby(day)
	)
	starts = [start for start, _end in buckets]
	totals = [0] * len(buckets)
	for on, amount in scoped(query, table, {}).run():
		totals[bisect_right(starts, on) - 1] += amount or 0
	return [float(total) for total in totals]
