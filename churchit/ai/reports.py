# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Explain this report: a short AI summary of a churchit script report the caller has run.

The server runs the report again as the caller with the filters the person set, through Frappe's
query_report.run, so the report's roles, the report permission on its doctype and User Permissions
apply as in the desk. It never takes rows from the browser. It sends the report's own columns, without
masked fields and PERSON_HEALTH_FIELDS, of at most MAX_ROWS rows. The rows are records of the report's
doctype and of each doctype its Link columns name, so a report on a doctype of Only for Local or Zero
Retention Models goes to the Private Work agent; so does a finance report, whose rows total gifts.
NO_EXPLAIN reports have no Explain item.
"""

import json

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.desk import query_report
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import strip_html_tags

from churchit.ai import runner
from churchit.ai.switch import require_ai

FEATURE = "Explain report"
ACCESS_LOG_METHOD = "AI: Explain report"
CHECK = "churchit.ai.reports.check_explanation"
# Reports about children, and reports whose rows can hold or reveal Private prayer requests.
NO_EXPLAIN = (
	"Active Prayer List",
	"Children",
	"Pastoral Care Watch List",
	"Prayer Requests Recently Answered",
	"Prayer Requests Recently Created",
)
# A finance report's rows total the church's gifts, whatever its doctype, so they count as Collection
# records.
FINANCES = "Church Finances"
MAX_ROWS = 200
MAX_QUESTIONS = 3
MAX_TEXT = 1000
PROMPT = (
	'Explain the report "{report}" to the church staff member who ran it. Use only the filters, '
	"columns and rows in the data block{part}. Answer with JSON: "
	'{{"summary": "two or three sentences on what the rows show", '
	'"trend": "one sentence on a change over time in the rows, or an empty string", '
	'"questions": ["three short questions the staff member could ask next"]}}. '
	"Give only numbers that are in the rows or that you count or add up from them. Do not judge, "
	"label or score any person."
)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=60 * 60, user_based=True)
def explain_report(report_name: str, filters: dict | str | None = None) -> dict:
	"""Start an AI explanation of a churchit script report, run again as the caller with *filters*. Changes data.

	It writes an Access Log row. Returns the token of the run, and the columns, rows and total_rows
	that the AI gets, for the dialog to show beside the answer. The answer, {summary, trend,
	questions}, reaches the caller's browser when the run ends; nothing is saved.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	report = get_explainable_report(report_name)
	filters = frappe.parse_json(filters) or {}
	if not isinstance(filters, dict):
		frappe.throw(_("Give the filters as an object of filter names and values."))

	result = query_report.run(
		report.name, filters=filters, ignore_prepared_report=True, are_default_filters=False
	)
	table = get_table(report.ref_doctype, result["columns"], result["result"])
	make_access_log(
		doctype=report.ref_doctype, report_name=report.name, filters=filters, method=ACCESS_LOG_METHOD
	)
	sends = {report.ref_doctype} | {
		column["options"]
		for column in result["columns"]
		if column.get("fieldtype") == "Link" and column.get("options")
	}
	if report.module == FINANCES:
		sends.add("Collection")
	run = runner.start(FEATURE, get_prompt(report.name, filters, table), sends=sends, check=CHECK)
	return {**run, **table}


def get_explainable_report(report_name: str):
	"""The Report record of a churchit script report that AI may explain, or a refusal."""
	if report_name in NO_EXPLAIN:
		frappe.throw(
			_(
				"AI does not explain this report, because it is about children or can hold private prayer requests."
			)
		)

	frappe.has_permission("Report", doc=report_name, throw=True)
	report = frappe.get_doc("Report", report_name)
	is_churchit = frappe.db.get_value("Module Def", report.module, "app_name") == "churchit"
	if report.report_type != "Script Report" or not is_churchit:
		frappe.throw(_("AI explains only churchit's script reports."))
	return report


def get_table(doctype: str, columns: list[dict], rows: list) -> dict:
	"""The report's columns and first MAX_ROWS rows as lists, without masked and health fields and the
	fields of *doctype* that the caller may not read.

	A Link value is replaced by the title that set_report_link_titles gave its row.
	"""
	meta = frappe.get_meta(doctype)
	readable = set(meta.get_permlevel_access("read"))
	hidden = {field.fieldname for field in meta.fields if field.permlevel and field.permlevel not in readable}
	hidden |= {field.fieldname for field in meta.get_masked_fields()}
	hidden |= set(runner.PERSON_HEALTH_FIELDS)
	kept = [
		(index, column)
		for index, column in enumerate(columns)
		if column.get("fieldname") not in hidden and not column.get("hidden")
	]
	return {
		"columns": [column.get("label") or column.get("fieldname") for _index, column in kept],
		"rows": [[get_cell(row, index, column) for index, column in kept] for row in rows[:MAX_ROWS]],
		"total_rows": len(rows),
	}


def get_cell(row: dict | list, index: int, column: dict):
	"""One value of a row, which a report gives as a dict or a list, as plain JSON."""
	if isinstance(row, dict):
		fieldname = column.get("fieldname")
		value = row.get(f"_{fieldname}_link_title") or row.get(fieldname)
	else:
		value = row[index] if index < len(row) else None
	if isinstance(value, str):
		return strip_html_tags(value)
	return value if isinstance(value, int | float | bool | type(None)) else str(value)


def get_prompt(report_name: str, filters: dict, table: dict) -> str:
	"""The instructions, then the filters, columns and rows as one data block."""
	part = ""
	if table["total_rows"] > len(table["rows"]):
		part = f" (the first {len(table['rows'])} of {table['total_rows']} rows)"
	data = json.dumps(
		{"filters": filters, "columns": table["columns"], "rows": table["rows"]},
		default=str,
		ensure_ascii=False,
	)
	return PROMPT.format(report=report_name, part=part) + "\n\n" + runner.wrap_data(data, "report rows")


def check_explanation(answer) -> dict:
	"""The answer as {summary, trend, questions} of text, or a refusal (runner check). The dialog
	shows the text escaped."""
	if not isinstance(answer, dict) or not isinstance(answer.get("summary"), str):
		frappe.throw(_(runner.UNUSABLE))
	questions = answer.get("questions")
	return {
		"summary": get_text(answer["summary"]),
		"trend": get_text(answer.get("trend")),
		"questions": [
			get_text(question)
			for question in (questions if isinstance(questions, list) else [])
			if isinstance(question, str) and question.strip()
		][:MAX_QUESTIONS],
	}


def get_text(text) -> str:
	return (text if isinstance(text, str) else "").strip()[:MAX_TEXT]
