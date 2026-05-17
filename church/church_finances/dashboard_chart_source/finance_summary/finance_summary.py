import frappe
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


@frappe.whitelist()
def get(
	chart_name=None,
	chart=None,
	no_cache=None,
	filters=None,
	from_date=None,
	to_date=None,
	timespan=None,
	time_interval=None,
	**kwargs,
):
	time_interval = time_interval or "Monthly"
	timespan = timespan or "Last Year"

	buckets = _buckets(timespan, time_interval, from_date, to_date)
	labels = [_label(start, time_interval) for start, _ in buckets]

	collections = [_sum_in_range("Collection", "date", "total_amount", s, e) for s, e in buckets]
	expenses = [_sum_in_range("Expense", "date", "amount", s, e) for s, e in buckets]

	return {
		"labels": labels,
		"datasets": [
			{"name": "Collections", "values": collections},
			{"name": "Expenses", "values": expenses},
		],
	}


def _buckets(timespan, time_interval, from_date, to_date):
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


def _label(start, time_interval):
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


def _sum_in_range(doctype, date_field, amount_field, start, end):
	total = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(`{amount_field}`), 0)
		FROM `tab{doctype}`
		WHERE docstatus = 1 AND `{date_field}` BETWEEN %s AND %s
		""",
		(start, end),
	)[0][0]
	return float(total or 0)
