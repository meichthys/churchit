# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The week at a glance for AI apps and the Church Office agent, as the caller."""

from datetime import date, timedelta

import frappe
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.utils import get_url_to_form, getdate

from churchit.ai.switch import require_ai
from churchit.church_people.ai import first_time_guests_without_follow_up, get_page, get_plain_text, with_url
from churchit.church_people.followup import CARD

# The records whose to-dos ask the caller to follow someone up.
FOLLOW_UP_DOCTYPES = (CARD, "Care Request")


@frappe.whitelist(methods=["GET"])
def get_week_overview(start: str | None = None) -> dict:
	"""What needs the caller's attention in the week (Monday to Sunday) of *start*, this week by default. Reads only.

	Returns week (its first and last day); functions, that week's functions; follow_ups, the caller's
	open to-dos on follow-up cards and care requests due by Sunday or with no date; and guests, the
	first-time guests of the last 30 days with no follow-up card. Each holds total and the first 50
	rows, and a part the caller may not read is left out.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	monday = getdate(start) - timedelta(days=getdate(start).weekday())
	sunday = monday + timedelta(days=6)
	overview = {"week": [monday, sunday], "follow_ups": get_follow_ups(sunday)}
	if frappe.has_permission("Function"):
		overview["functions"] = get_functions(monday, sunday)
	if frappe.has_permission("Person") and frappe.has_permission(CARD):
		overview["guests"] = first_time_guests_without_follow_up()
	return overview


def get_functions(monday: date, sunday: date) -> dict:
	functions = frappe.get_list(
		"Function",
		filters={"start_date": ("between", [monday, sunday]), "auto_repeat": 0},
		fields=["name", "title", "start_date", "start_time", "did_not_meet"],
		order_by="start_date asc, start_time asc",
	)
	return get_page([with_url("Function", function) for function in functions])


def get_follow_ups(sunday: date) -> dict:
	"""The caller's open to-dos on follow-up cards and care requests, due by *sunday* or with no date."""
	todos = frappe.get_list(
		"ToDo",
		filters={
			"allocated_to": frappe.session.user,
			"status": "Open",
			"reference_type": ("in", FOLLOW_UP_DOCTYPES),
		},
		or_filters=[["date", "<=", sunday], ["date", "is", "not set"]],
		fields=["reference_type", "reference_name", "date", "description"],
		order_by="date asc",
	)
	return get_page(
		[
			{
				"reference_type": todo.reference_type,
				"reference_name": todo.reference_name,
				"due": todo.date,
				"description": get_plain_text(todo.description),
				"url": get_url_to_form(todo.reference_type, todo.reference_name),
			}
			for todo in todos
		]
	)


def queue_weekly_notes() -> None:
	"""Monday cron: queue one weekly AI note job for each user who asked for one (A7.2)."""
