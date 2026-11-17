# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Function Link search that offers the coming functions first.

Frappe's own search takes the functions with the latest dates and then sorts them by name, so with
recurring functions made weeks ahead, this Sunday's service is often not in the list at all.
"""

import frappe
from frappe.utils import format_time, getdate
from frappe.utils.data import make_filter_tuple

from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_people.search import get_searched_fields

FUNCTION = "Function"


@frappe.whitelist(methods=["GET"])
@frappe.validate_and_sanitize_search_inputs
def search_functions(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict | list | None,
	as_dict: bool = False,
	reference_doctype: str | None = None,
) -> list:
	"""Function Link search: functions from today on, soonest first, then past ones, latest first. Reads only.

	hooks.py makes it the standard_queries for Function. It reads through `frappe.get_list` like Frappe
	does, so the user's church and the field's filters apply as usual. A row is the name, the title, the
	type and the start time.
	"""
	if isinstance(filters, dict):
		filters = [make_filter_tuple(FUNCTION, key, value) for key, value in filters.items()]
	filters = filters or []
	or_filters = []
	if txt:
		fields = get_searched_fields(frappe.get_meta(FUNCTION))
		or_filters = [[FUNCTION, field, "like", f"%{txt}%"] for field in fields]

	today = getdate()
	wanted = start + page_len
	arguments = {"or_filters": or_filters, "reference_doctype": reference_doctype}
	rows = get_functions([*filters, [FUNCTION, "start_date", ">=", today]], "asc", wanted, **arguments)
	if len(rows) < wanted:
		rows += get_functions(
			[*filters, [FUNCTION, "start_date", "<", today]], "desc", wanted - len(rows), **arguments
		)

	results = []
	for row in rows[start:wanted]:
		time = format_time(row.start_time, TIME_FORMAT) if row.start_time and not row.all_day else None
		result = frappe._dict(name=row.name, label=row.title, type=row.type, time=time)
		results.append(result if as_dict else tuple(result.values()))
	return results


def get_functions(filters: list, order: str, limit: int, **arguments) -> list[frappe._dict]:
	"""Up to *limit* functions that match *filters*, by date and time in *order*."""
	return frappe.get_list(
		FUNCTION,
		filters=filters,
		fields=["name", "title", "type", "start_time", "all_day"],
		order_by=f"start_date {order}, start_time {order}",
		limit=limit,
		strict=False,
		**arguments,
	)
