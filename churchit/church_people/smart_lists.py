# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Smart lists: saved reports of people, which Frappe keeps, scopes and refreshes.

A smart list is a Report Builder report on Person, or a Custom Report (menu > Save) of a script report in
`REPORT_LISTS`, run with its saved filters. A follow-up workflow starts cards from one, a Pathway step
reads one and a Church Email is sent to one, all through `get_people`.
"""

import json

import frappe
from frappe import _

from churchit.church_people.membership import living_people_filter
from churchit.church_scope import church_filters

SMART_LIST = ("Report Builder", "Person")
CUSTOM_REPORT = "Custom Report"
# Script reports on Person whose rows each name one person in `person`.
REPORT_LISTS = ("Attendance Count",)


def is_smart_list(report: str | None) -> bool:
	"""True when *report* is a saved Report Builder report on Person or a Custom Report of a `REPORT_LISTS` report."""
	if not report:
		return False
	values = frappe.db.get_value("Report", report, ["report_type", "ref_doctype", "reference_report"])
	if not values:
		return False
	report_type, ref_doctype, reference_report = values
	if report_type == CUSTOM_REPORT:
		return reference_report in REPORT_LISTS
	return (report_type, ref_doctype) == SMART_LIST


def get_people(report: str, church: str | None) -> list[str]:
	"""The living people of *church* on the smart list *report*, worked out now."""
	if not is_smart_list(report):
		frappe.throw(
			_(
				"{0} is not a smart list: a saved Report Builder list of people or a saved Attendance Count."
			).format(report)
		)
	source = frappe.get_doc("Report", report)
	if source.report_type == CUSTOM_REPORT:
		params = {"filters": [["Person", "name", "in", get_report_people(source)]]}
	else:
		params = json.loads(source.json or "{}")
	filters = source.get_standard_report_filters(params, church_filters(church))
	return frappe.get_all("Person", filters=[*filters, living_people_filter()], pluck="name", distinct=True)


def get_report_people(source) -> list[str]:
	"""The people the Custom Report *source* shows the reader: its script report run with its saved filters."""
	if source.reference_report not in REPORT_LISTS:
		frappe.throw(_("{0} is not a smart list.").format(source.name))
	saved = json.loads(source.json or "{}").get("filters") or {}
	rows = frappe.get_doc("Report", source.reference_report).execute_module(frappe._dict(saved))[1]
	return [row["person"] for row in rows]


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_smart_lists(doctype, txt, searchfield, start, page_len, filters) -> list[list[str]]:
	"""Link search for a smart list field: the reader's Report Builder lists on Person and saved `REPORT_LISTS`."""
	return frappe.get_list(
		"Report",
		filters={"name": ("like", f"%{txt}%"), "ref_doctype": SMART_LIST[1]},
		or_filters={"report_type": SMART_LIST[0], "reference_report": ("in", REPORT_LISTS)},
		fields=["name"],
		order_by="name asc",
		limit_start=start,
		limit_page_length=page_len,
		as_list=True,
	)
