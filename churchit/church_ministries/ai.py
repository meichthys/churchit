# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What AI apps and the Church Office agent read about serving, as the caller."""

from urllib.parse import urlencode

import frappe
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.utils import add_days, get_url_to_form, get_url_to_report_with_filters, getdate

from churchit.ai.switch import require_ai
from churchit.church_people.ai import get_page, get_report_rows, get_window

SCHEDULE = "Ministry Team Schedule"
DEFAULT_DAYS = 7


@frappe.whitelist(methods=["GET"])
def get_open_needs(start: str | None = None, end: str | None = None) -> dict:
	"""Open ministry team positions at functions from *start* to *end*, today and the next 7 days by default. Reads only.

	As the Ministry Team Schedule report shows them to the caller; at most 92 days. Returns total,
	rows (the first 50 by date: date, function, function_title, position, position_title, needed,
	accepted, pending, open, asked (the people asked and their answers), url) and url, the report
	for these dates.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	start, end = get_window(start, end, (getdate(), add_days(getdate(), DEFAULT_DAYS)))
	filters = {"from_date": start, "to_date": end, "only_open": 1}
	rows = [get_need(row) for row in get_report_rows(SCHEDULE, filters)]
	return get_page(rows, get_url_to_report_with_filters(SCHEDULE, urlencode(filters)))


def get_need(row: frappe._dict) -> dict:
	"""One row of the Ministry Team Schedule report, for an AI app."""
	return {
		"date": row.start_date,
		"function": row.function,
		"function_title": row.get("_function_link_title") or row.function,
		"position": row.position,
		"position_title": row.get("_position_link_title") or row.position,
		"needed": row.needed,
		"accepted": row.accepted,
		"pending": row.pending,
		"open": row.open,
		"asked": row.people,
		"url": get_url_to_form("Function", row.function),
	}
