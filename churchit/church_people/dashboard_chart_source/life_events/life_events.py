import json

import frappe
from frappe import _
from frappe.query_builder.functions import Count

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
	"""Count of one Life Event type per period, limited to people the user may see.

	The event type comes from the chart's own filters, so one source serves
	the baptism and membership charts alike.
	"""
	frappe.has_permission("Person", "report", throw=True)
	event_type = event_type_filter(filters)
	buckets = time_buckets(timespan or "Last Year", time_interval or "Monthly", from_date, to_date)
	return {
		"labels": [bucket_label(start, time_interval or "Monthly") for start, _ in buckets],
		"datasets": [{"name": event_type, "values": [count_events(event_type, s, e) for s, e in buckets]}],
	}


def event_type_filter(filters):
	rows = json.loads(filters) if isinstance(filters, str) else (filters or [])
	for row in rows:
		if row[1] == "event_type":
			return row[3]
	frappe.throw(_("The chart's filters must name an event_type."))


def count_events(event_type, start, end):
	Person = frappe.qb.DocType("Person")
	LifeEvent = frappe.qb.DocType("Life Event")
	query = (
		frappe.qb.from_(LifeEvent)
		.join(Person)
		.on((LifeEvent.parent == Person.name) & (LifeEvent.parenttype == "Person"))
		.select(Count("*"))
		.where((LifeEvent.event_type == event_type) & LifeEvent.date.between(start, end))
	)
	return scoped(query, Person, {}).run()[0][0]
