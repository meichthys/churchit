import frappe
from frappe.query_builder.functions import Count
from frappe.utils import (
	add_days,
	add_months,
	add_to_date,
	formatdate,
	get_first_day,
	get_first_day_of_week,
	get_last_day,
	get_quarter_ending,
	get_quarter_start,
	get_year_ending,
	get_year_start,
	getdate,
)

from churchit.church_scope import church_query_filters, scoped


@frappe.whitelist()
def count_weekly_attendance():
	frappe.has_permission("Function", "report", throw=True)
	last_week = frappe.utils.add_days(frappe.utils.nowdate(), -7)

	Attendance = frappe.qb.DocType("Function Attendance")
	Function = frappe.qb.DocType("Function")

	query = (
		frappe.qb.from_(Attendance)
		.join(Function)
		.on(Attendance.parent == Function.name)
		.select(Count(Attendance.name))
		.where(Function.start_date >= last_week)
	)
	count = scoped(query, Function, {}).run()[0][0]

	return {
		"value": count or 0,
		"fieldtype": "Int",
		"route": ["List", "Function"],
		"route_options": {"start_date": [">=", last_week]},
	}


@frappe.whitelist()
def count_people(filters: str | list | dict | None = None):
	"""Number card: people matching the card's filters in the reader's churches."""
	return count_in_readers_churches("Person", filters)


@frappe.whitelist()
def count_families(filters: str | list | dict | None = None):
	"""Number card: families matching the card's filters in the reader's churches."""
	return count_in_readers_churches("Family", filters)


def count_in_readers_churches(doctype, filters):
	"""Count *doctype* like a Document Type card would, but only in the reader's churches.

	Every church reads the people directory, so Frappe's own count totals the
	whole organisation for a branch.
	"""
	frappe.has_permission(doctype, "report", throw=True)
	scope = church_query_filters({})
	rows = [
		*(frappe.parse_json(filters) or []),
		*([doctype, field, *condition] for field, condition in scope.items()),
	]
	return {
		"value": frappe.db.count(doctype, filters=rows),
		"fieldtype": "Int",
		"route": ["List", doctype],
		"route_options": {row[1]: [row[2], row[3]] for row in rows},
	}


def time_buckets(timespan, time_interval, from_date, to_date):
	today = getdate()
	if timespan == "Select Date Range" and from_date and to_date:
		start, end = getdate(from_date), getdate(to_date)
	else:
		end = today
		start_map = {
			"Last Year": add_to_date(today, years=-1, as_datetime=False),
			"Last Quarter": add_months(today, -3),
			"Last Month": add_months(today, -1),
			"Last Week": add_days(today, -7),
		}
		start = getdate(start_map.get(timespan, add_to_date(today, years=-1, as_datetime=False)))

	step_map = {
		"Daily": lambda d: (d, d),
		"Weekly": lambda d: (get_first_day_of_week(d), add_days(get_first_day_of_week(d), 6)),
		"Monthly": lambda d: (get_first_day(d), get_last_day(d)),
		"Quarterly": lambda d: (getdate(get_quarter_start(d)), getdate(get_quarter_ending(d))),
		"Yearly": lambda d: (getdate(get_year_start(d)), getdate(get_year_ending(d))),
	}
	step = step_map.get(time_interval, step_map["Monthly"])
	advance = {
		"Daily": lambda d: add_days(d, 1),
		"Weekly": lambda d: add_days(d, 7),
		"Monthly": lambda d: add_months(d, 1),
		"Quarterly": lambda d: add_months(d, 3),
		"Yearly": lambda d: add_to_date(d, years=1, as_datetime=False),
	}.get(time_interval, lambda d: add_months(d, 1))

	cursor = step(start)[0]
	buckets = []
	while cursor <= end:
		bucket_start, bucket_end = step(cursor)
		buckets.append((bucket_start, bucket_end))
		cursor = advance(cursor)
	return buckets


def bucket_label(start, time_interval):
	if time_interval == "Daily":
		return formatdate(start, "d MMM")
	if time_interval == "Weekly":
		return formatdate(start, "d MMM")
	if time_interval == "Quarterly":
		quarter = (start.month - 1) // 3 + 1
		return f"Q{quarter} {start.year}"
	if time_interval == "Yearly":
		return str(start.year)
	return formatdate(start, "MMM YYYY")
