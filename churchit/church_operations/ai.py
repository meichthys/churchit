# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Action items from meeting minutes, as Church Task drafts that a Church Manager checks and saves.

Meeting Minutes are staff records, so a run sends them only as Private Work (the private doctypes of
Church AI Settings decide). Each proposed task opens filled and unsaved through churchit.ai.drafts;
the person picks its owner with Assign To after saving, so the AI never assigns anyone.
"""

import json

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.utils import html_to_plain_text
from frappe.rate_limiter import rate_limit
from frappe.utils import get_datetime

from churchit.ai import runner
from churchit.ai.drafts import make_draft
from churchit.ai.switch import require_ai
from churchit.church_people.ai_actions import (
	HOUR,
	JSON_ONLY,
	RUNS_AN_HOUR,
	check_text,
	get_date,
	to_paragraphs,
)

ACTION_ITEMS = "Action items"
MAX_MINUTES = 12000
MAX_TASKS = 20
MAX_TITLE = 140
# The Meeting Minutes fields the prompt sends.
MINUTES_FIELDS = ("title", "meeting_date", "minutes")

INSTRUCTIONS = """List the action items in the meeting minutes in the data block: what someone agreed to do.
{json_only} Shape: {{"tasks": [{{"title": "...", "owner": "the name the minutes give, or empty", "due_date": "YYYY-MM-DD or empty", "priority": "{priorities}", "notes": "..."}}]}}.
Take each task from the minutes and add none; at most {most}. The meeting was on {meeting_date}."""


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def action_items(minutes: str) -> dict:
	"""Start an AI run that finds the action items in Meeting Minutes, as Church Task drafts. Changes data.

	For a Church Manager. The prompt holds the minutes' title, date and text. The answer comes to your
	browser as proposed tasks, each with a link that opens it filled and unsaved; save the ones to
	keep and assign them with Assign To.
	"""
	require_ai()
	frappe.only_for("Church Manager", message=True)
	record = frappe.get_doc("Meeting Minutes", minutes)
	record.check_permission("read")
	frappe.has_permission("Church Task", "create", throw=True)
	record.apply_fieldlevel_read_permissions()
	sent = {field: record.get(field) for field in MINUTES_FIELDS}
	sent["minutes"] = check_text(html_to_plain_text(sent["minutes"]), MAX_MINUTES)

	instructions = INSTRUCTIONS.format(
		json_only=JSON_ONLY,
		priorities=" | ".join(get_priorities()),
		most=MAX_TASKS,
		meeting_date=record.meeting_date,
	)
	data = runner.wrap_data(json.dumps(sent, default=str, indent=1), "meeting minutes")
	make_access_log(doctype="Meeting Minutes", document=record.name, method=f"AI: {ACTION_ITEMS}")
	return runner.start(
		ACTION_ITEMS,
		f"{instructions}\n\n{data}",
		sends=("Meeting Minutes",),
		reference_doctype="Meeting Minutes",
		reference_name=record.name,
		check="churchit.church_operations.ai.check_action_items",
	)


def get_priorities() -> list[str]:
	return [option for option in frappe.get_meta("Church Task").get_options("priority").split("\n") if option]


def check_action_items(answer: dict) -> dict:
	"""The runner's check for action_items: each task as a Church Task draft of the caller.

	A task keeps a title, a real due date, a listed priority and its notes as text; owner is only
	shown. Returns tasks: title, owner, due_date, priority and url, the unsaved form.
	"""
	tasks = answer.get("tasks") if isinstance(answer, dict) else None
	if not isinstance(tasks, list):
		frappe.throw(_("The AI answer could not be used."))
	drafts = [get_task_draft(task) for task in tasks[:MAX_TASKS] if isinstance(task, dict)]
	drafts = [draft for draft in drafts if draft]
	if not drafts:
		frappe.throw(_("The AI found no action items in these minutes."))
	return {"tasks": drafts}


def get_task_draft(task: dict) -> dict | None:
	"""One proposed task as a Church Task draft, or None when it has no title."""
	title = " ".join(str(task.get("title") or "").split())[:MAX_TITLE]
	if not title:
		return None
	due_date = get_date(task.get("due_date"))
	values = {
		"title": title,
		"due_date": str(get_datetime(due_date)) if due_date else None,
		"priority": task.get("priority") if task.get("priority") in get_priorities() else None,
		"notes": to_paragraphs(str(task.get("notes") or "")) or None,
	}
	values = {field: value for field, value in values.items() if value}
	return {
		"title": title,
		"owner": " ".join(str(task.get("owner") or "").split())[:MAX_TITLE],
		"due_date": due_date,
		"priority": values.get("priority"),
		"url": make_draft("Church Task", values, source=_(ACTION_ITEMS))["url"],
	}
