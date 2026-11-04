import frappe

from churchit.church_scope import church_query_filters
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
	"""People added per period in the reader's churches.

	Every church reads the people directory, so Frappe's own Count chart
	totals the whole organisation for a branch. The period is the one the
	user picked, else the chart's own.
	"""
	frappe.has_permission("Person", "report", throw=True)
	if chart_name:
		chart_doc = frappe.get_doc("Dashboard Chart", chart_name)
		timespan, time_interval = timespan or chart_doc.timespan, time_interval or chart_doc.time_interval
	time_interval = time_interval or "Weekly"
	scope = church_query_filters({})
	buckets = time_buckets(timespan or "Last Year", time_interval, from_date, to_date)
	values = [
		# Frappe already reads a date range as reaching the end of its last day.
		frappe.db.count("Person", {"creation": ["between", [start, end]], **scope})
		for start, end in buckets
	]
	return {
		"labels": [bucket_label(start, time_interval) for start, _ in buckets],
		"datasets": [{"name": "People", "values": values}],
	}
