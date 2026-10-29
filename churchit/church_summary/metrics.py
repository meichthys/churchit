# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The stored Weekly Metrics rows: one row per church and week.

Attendance, first-time visitors and giving come from dated records, so a rerun corrects a week
after a late check-in or a late collection. The other people counts are the state on the day the
row is written, so only the current week gets them. A backfill keeps a row's stored people counts
(0 on a new row).

On a single-church site one row, for the root church, counts the whole site. With multi-church on,
a shared Function counts once, for the church in `shared_by_church`, so a chart that adds the rows
of several churches counts a joint service once.
"""

import frappe
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_days, cint, flt, get_first_day_of_week, today

from churchit.church_people.membership import is_active_member, living_people_filter
from churchit.church_scope import SHARED, is_multi_church, root_church

BACKFILL_WEEKS = 52
BACKFILL_JOB = "weekly_metrics_backfill"
BACKFILL_ROLES = ("Church Manager", "System Manager")


def record_week(week_start, include_people: bool = False) -> None:
	"""Write one Weekly Metrics row per church for the week that holds *week_start*."""
	week_start = get_first_day_of_week(week_start)
	week_end = add_days(week_start, 6)
	multi_church = is_multi_church()
	churches = frappe.get_all("Church", pluck="name") if multi_church else [root_church()]
	for church in filter(None, churches):
		scope = church if multi_church else None
		values = {
			"attendance": get_attendance(scope, week_start, week_end),
			"first_time_visitors": get_first_time_visitors(scope, week_start, week_end),
			**get_giving(scope, week_start, week_end),
		}
		if include_people:
			values.update(get_people_counts(scope))
		save_row(church, week_start, values)


def save_row(church: str, week_start, values: dict) -> None:
	"""Update the church's row for the week, or add it. The fields not in *values* keep their value."""
	name = frappe.db.get_value(
		"Weekly Metrics", {"church": church, "week_start": week_start}, "name", for_update=True
	)
	row = frappe.get_doc("Weekly Metrics", name) if name else frappe.new_doc("Weekly Metrics")
	row.update({"church": church, "week_start": week_start, **values})
	row.save(ignore_permissions=True)


def get_attendance(church: str | None, week_start, week_end) -> int:
	"""The head counts of the week's Functions: `attendance_total` is the one counted rule."""
	# church-scope: a job over every church; each row counts only its own church, a shared Function in the church that shared it
	Function = frappe.qb.DocType("Function")
	query = (
		frappe.qb.from_(Function)
		.select(Sum(Function.attendance_total))
		.where(Function.start_date[week_start:week_end] & (Function.auto_repeat == 0))
	)
	if church:
		query = query.where(
			(Function.church == church)
			| ((Function.church == SHARED) & (Function.shared_by_church == church))
		)
	return cint(query.run()[0][0])


def get_first_time_visitors(church: str | None, week_start, week_end) -> int:
	# church-scope: a job over every church; each row counts only its own church
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Person)
		.select(Count(Person.name))
		.where(Person.first_attended_on[week_start:week_end])
	)
	if church:
		query = query.where(Person.church == church)
	return cint(query.run()[0][0])


def get_giving(church: str | None, week_start, week_end) -> dict:
	"""The total of the week's submitted Collections, and the people who gave in them."""
	# church-scope: a job over every church; each row counts only its own church, and money is never shared
	Collection = frappe.qb.DocType("Collection")
	Donation = frappe.qb.DocType("Donation")
	week = (Collection.docstatus == 1) & Collection.date[f"{week_start} 00:00:00" : f"{week_end} 23:59:59"]
	if church:
		week &= Collection.church == church

	giving_total = frappe.qb.from_(Collection).select(Sum(Collection.total_amount)).where(week).run()[0][0]
	givers = (
		frappe.qb.from_(Donation)
		.join(Collection)
		.on((Donation.parent == Collection.name) & (Donation.parenttype == "Collection"))
		.select(Count(Donation.person).distinct())
		.where(week & (Donation.person != ""))
		.run()[0][0]
	)
	return {"giving_total": flt(giving_total), "givers": cint(givers)}


def get_people_counts(church: str | None) -> dict:
	"""Today's counts of the church's living people: active members, people in groups and people serving."""
	# church-scope: a job over every church; each row counts only its own church
	Person = frappe.qb.DocType("Person")
	living = living_people_filter(Person)
	if church:
		living &= Person.church == church

	def count(criterion):
		return cint(frappe.qb.from_(Person).select(Count(Person.name)).where(living & criterion).run()[0][0])

	return {
		"active_members": count(is_active_member(Person)),
		"people_in_groups": count(Person.group_count > 0),
		"people_serving": count(Person.times_served_90d > 0),
	}


def record_recent_weeks() -> None:
	"""Daily job: this week with people counts, and last week's attendance and giving again."""
	this_week = get_first_day_of_week(today())
	record_week(add_days(this_week, -7))
	record_week(this_week, include_people=True)


@frappe.whitelist(methods=["POST"])
def backfill() -> None:
	"""Queue the 52-week attendance and giving backfill (Church Manager)."""
	frappe.only_for(BACKFILL_ROLES)
	frappe.enqueue(
		backfill_weeks, queue="long", job_id=BACKFILL_JOB, deduplicate=True, enqueue_after_commit=True
	)


def backfill_weeks(weeks: int = BACKFILL_WEEKS) -> None:
	"""Long job: attendance and giving for the *weeks* before this one, one commit per week.

	It skips last week: the daily job writes that row, and two jobs that add one row at once collide.
	"""
	this_week = get_first_day_of_week(today())
	for weeks_back in range(2, weeks + 1):
		record_week(add_days(this_week, -7 * weeks_back))
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (keep each recorded week)
