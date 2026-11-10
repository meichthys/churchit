# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Churchit's own AI actions on people: describe a list, brief me, draft a note, map an import.

Each action is a POST from a desk button. It checks the caller's rights on what it reads, builds the
prompt from the fields named beside it and starts a run through churchit.ai.runner, which picks
Writer or Private Work from the doctypes the prompt holds and checks the model's label. The answer
reaches the caller's browser only through the check named for the run, which runs as the caller and
keeps what the caller could choose in the desk. Nothing is saved by itself: a note draft opens as an
unsaved form through churchit.ai.drafts, and a mapping waits in the import form for its save.
"""

import json
from datetime import date
from typing import get_args
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.model import get_permitted_fields, no_value_fields
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, escape_html, get_url_to_form, today
from frappe.utils.data import TimespanOptions

from churchit.ai import opt_outs, runner
from churchit.ai.switch import require_ai
from churchit.church_people import ai as people_ai
from churchit.church_people import notes
from churchit.church_people.followup import CARD
from churchit.dashboard import count_people

RUNS_AN_HOUR = 20
HOUR = 60 * 60
DESCRIBE_PEOPLE = "Describe people"
BRIEF_ME = "Brief me"
NOTE_DRAFT = "Note draft"
IMPORT_MAPPING = "Import mapping"
CHECKS = "churchit.church_people.ai_actions"
MAX_REQUEST = 1000
MAX_DICTATION = 6000
MAX_CHOICES = 200
MAX_SUMMARY = 2000
MAX_TEXT = 6000
# The Person and table fields a description filters on; the others hold text, files or layout.
FILTER_TYPES = ("Check", "Data", "Date", "Datetime", "Int", "Link", "Select")
# The only doctypes whose names a description gets as Link values: choices the church sets up. A Link
# to any other doctype, such as Person, Family, User or Address, names no value.
CHOICE_DOCTYPES = (
	"Address Type",
	"Church",
	"Email Type",
	"Group",
	"Inactive Reason",
	"Life Event Type",
	"Marital Status",
	"Member Status",
	"Membership Type",
	"Ministry",
	"Ministry Team Position",
	"Person Relation Type",
	"Phone Type",
	"Position Type",
	"Salutation",
	"Skill",
)
# What a briefing sends: each part of churchit.church_people.ai's briefing, and the doctype of the
# records in it. records holds timeline cards, whose doctypes come from their links (RECORD_DOCTYPES).
BRIEF_PARTS = {
	"Person": {
		"summary": "Person",
		"household": "Family",
		"groups": "Person",
		"ministry_teams": "Person",
		"team_positions": "Person",
		"open_follow_ups": CARD,
		"records": "Person",
	},
	"Group": {
		"summary": "Group",
		"member_count": "Group",
		"members": "Person",
		"leaders": "Person",
		"meetings": "Function",
		"open_join_requests": "Group Join Request",
	},
}
RECORD_DOCTYPES = ("Visitation Log", "Care Request", "Member Transfer", "Connection Card", "Person Note")
# The parts of a briefing that list people, each row naming one in "person".
PEOPLE_PARTS = ("household", "members", "leaders", "open_join_requests")
# Person summary fields that churchit works out from giving, care and background check records
# (church_people/summaries), and those records' doctype. A field of no value says nothing and is left out.
SUMMARY_SOURCES = {
	"first_gift_on": "Collection",
	"last_gift_on": "Collection",
	"is_lapsed_giver": "Collection",
	"open_care_requests": "Care Request",
	"last_visited_on": "Visitation Log",
	"background_check_status": "Background Check",
	"background_check_expires_on": "Background Check",
}
# What a note draft fills, the field that holds its text, and the check of its answer.
NOTE_DRAFTS = {
	"Person Note": {
		"fields": ("category", "contact_method", "noted_on", "note"),
		"text": "note",
		"check": f"{CHECKS}.check_person_note",
	},
	"Visitation Log": {
		"fields": ("visit_type", "visit_date", "status", "duration_minutes", "follow_up_needed", "notes"),
		"text": "notes",
		"check": f"{CHECKS}.check_visitation_log",
	},
}
# How the shape of a note answer shows each field type; any other field takes text.
EXAMPLES = {"Date": "YYYY-MM-DD", "Int": 0, "Check": False}
SOURCE_TITLES = ("title", "full_name", "person_name", "workflow", "text")
JSON_ONLY = "Answer with one JSON object and nothing else."

DESCRIBE_INSTRUCTIONS = """Turn the description of people in the data block into filters on Person, the church's directory.
{json_only} Shape: {{"filters": [[doctype, fieldname, operator, value], ...]}}.
doctype is Person or one of the tables below. Use only the fields and values listed; for a value listed as name (title), use the name. Operators: =, !=, >, <, >=, <=, like, not like, in, not in, is (value "set" or "not set"), between (value [from, to]) and Timespan (a value from the Timespan list). Dates are YYYY-MM-DD; today is {today}. Use at most 10 filters, and leave out what the fields cannot express."""

BRIEF_INSTRUCTIONS = """Write a short briefing for church staff about the {subject} in the data block, from those facts only.
{json_only} Shape: {{"summary": "..."}}, plain text of at most 120 words.
Give facts with their dates. Do not judge, label, score, rank or guess about anyone's faith, health, character or worth, and give no advice. Leave out what the data does not say."""

NOTE_INSTRUCTIONS = """Turn the notes in the data block, which a church worker dictated after talking with a person, into a {doctype} draft.
{json_only} Shape: {shape}.
Use only the values listed for each field, or leave the field out. Dates are YYYY-MM-DD; today is {today}, and a date the notes do not give is today. Write the {text_field} as clear sentences that keep every fact of the notes and add none.
Values: {choices}"""

IMPORT_INSTRUCTIONS = """Match each spreadsheet heading in the data block to a field of the import "{doctype}".
{json_only} Shape: {{"import": "{doctype}", "mapping": [{{"column": <the heading's number>, "field": "<fieldname>"}}, ...]}}.
Use only the fieldnames listed, each at most once. Leave out a heading that matches no field.
Fields: {fields}"""


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def describe_people(text: str) -> dict:
	"""Start an AI run that turns a description of people into People list filters. Changes data.

	The prompt holds the description, the Person fields you may read with their labels and choices,
	and the names of groups, ministries and skills; never a person. The answer comes to your browser
	as the filters in plain words with their count, checked as get_smart_list_url checks them.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	frappe.has_permission("Person", throw=True)
	request = check_text(text, MAX_REQUEST)
	instructions = DESCRIBE_INSTRUCTIONS.format(json_only=JSON_ONLY, today=today())
	prompt = "\n\n".join((instructions, get_person_schema(), runner.wrap_data(request, "description")))
	return runner.start(DESCRIBE_PEOPLE, prompt, check=f"{CHECKS}.check_people_filters")


def get_person_schema() -> str:
	"""The Person fields and table fields the caller may filter on, with labels, choices and Timespan values."""
	person = frappe.get_meta("Person")
	lines = ["Person fields:"]
	lines += get_field_lines("Person", get_permitted_fields("Person"))
	for table in person.get_table_fields():
		if table.permlevel in person.get_permlevel_access("read") and frappe.has_permission(
			table.options, parent_doctype="Person"
		):
			lines.append(f"Table {table.options} ({table.label}):")
			lines += get_field_lines(table.options, get_permitted_fields(table.options, parenttype="Person"))
	lines.append("Timespan values: " + ", ".join(get_args(TimespanOptions)))
	return "\n".join(lines)


def get_field_lines(doctype: str, readable: list[str]) -> list[str]:
	"""One line per field of *doctype* in *readable* that a filter can use, as fieldname: label (type: choices)."""
	lines = []
	for df in frappe.get_meta(doctype).fields:
		usable = (
			df.fieldtype in FILTER_TYPES and not df.hidden and df.fieldname not in runner.PERSON_HEALTH_FIELDS
		)
		if usable and df.fieldname in readable:
			lines.append(f"- {df.fieldname}: {df.label} ({df.fieldtype}{get_choices_text(df)})")
	return lines


def get_choices_text(df) -> str:
	"""The values a Select or Link field takes, as ": a, b"; a Link outside CHOICE_DOCTYPES names none."""
	if df.fieldtype == "Select":
		values = [option for option in (df.options or "").split("\n") if option]
	elif df.fieldtype == "Link" and df.options in CHOICE_DOCTYPES and frappe.has_permission(df.options):
		values = get_link_values(df.options)
	else:
		return f" to {df.options}" if df.fieldtype == "Link" else ""
	return ": " + ", ".join(values)


def get_link_values(doctype: str) -> list[str]:
	"""The records of *doctype* the caller may read, as name, or "name (title)" when it has a title field."""
	title = frappe.get_meta(doctype).title_field
	fields = ["name", title] if title and title != "name" else ["name"]
	rows = frappe.get_list(doctype, fields=fields, order_by="name asc", limit=MAX_CHOICES, as_list=True)
	return [
		f"{row[0]} ({row[1]})" if len(row) > 1 and row[1] and row[1] != row[0] else row[0] for row in rows
	]


def check_people_filters(answer: dict) -> dict:
	"""The runner's check for describe_people: the filters as get_smart_list_url checks and counts them.

	Returns filters (living people only unless a filter names is_deceased, in the reader's churches),
	count, words (each filter in plain words) and notes (the limits the filters add).
	"""
	filters = answer.get("filters") if isinstance(answer, dict) else None
	if not filters:
		frappe.throw(_("The AI found no filters in the description. Describe the people another way."))
	rows = people_ai.validate_person_filters(filters)[0]
	notes = []
	if not any(row[1] == "is_deceased" for row in rows):
		rows.insert(0, people_ai.LIVING)
		notes.append(_("Living people only."))
	scoped = people_ai.in_readers_churches(rows)
	if len(scoped) > len(rows):
		notes.append(_("Only the churches you may see."))
	return {
		"filters": scoped,
		"count": count_people(rows)["value"],
		"words": [people_ai.describe_filter(row) for row in rows if row != people_ai.LIVING],
		"notes": notes,
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def brief(doctype: str, name: str) -> dict:
	"""Start an AI run that summarizes a Person or a Group from what you may read about it. Changes data.

	The prompt holds the briefing that get_person_briefing or get_group_briefing gives you, which the
	Access Log keeps, without links and medical or emergency contact fields, and without the people and
	records that keep away from churchit's AI (a person or group that does is refused). A briefing that
	holds a record of a private doctype (Church AI Settings) runs on Private Work. Returns token and
	sources, the records the briefing used; the summary comes to your browser and is never stored.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	if doctype not in BRIEF_PARTS:
		frappe.throw(_("Brief Me works on a person or a group."))
	frappe.has_permission(doctype, doc=name, throw=True)
	opt_outs.refuse_kept_away(doctype, name)
	briefing = without_kept_away(get_briefing(doctype, name))
	facts = get_brief_facts(doctype, briefing)
	instructions = BRIEF_INSTRUCTIONS.format(subject=doctype.lower(), json_only=JSON_ONLY)
	data = runner.wrap_data(json.dumps(facts, default=str, indent=1), "briefing")
	run = runner.start(
		BRIEF_ME,
		f"{instructions}\n\n{data}",
		sends=tuple(sorted(get_brief_sends(doctype, briefing, facts))),
		reference_doctype=doctype,
		reference_name=name,
		check=f"{CHECKS}.check_brief",
	)
	return {**run, "sources": get_sources(list(briefing.values()))}


def get_briefing(doctype: str, name: str) -> dict:
	"""The office briefing of a Person or a Group, read as the caller; it writes its own Access Log row."""
	if doctype == "Person":
		return people_ai.get_person_briefing(name)
	return people_ai.get_group_briefing(name)


def without_kept_away(briefing: dict) -> dict:
	"""*briefing* without what churchit's AI features leave out (churchit.ai.opt_outs): each person who
	keeps their details out of AI or whose church keeps away from AI, the spouse among them, and each
	follow-up card and timeline card of a church that keeps away."""
	kept = opt_outs.get_kept_away_records(get_brief_records(briefing))
	briefing = dict(briefing)
	for part in (*PEOPLE_PARTS, "open_follow_ups"):
		if briefing.get(part):
			briefing[part] = [row for row in briefing[part] if get_row_record(part, row) not in kept]
	if briefing.get("records"):
		rows = [row for row in briefing["records"]["rows"] if get_card_record(row) not in kept]
		briefing["records"] = {**briefing["records"], "rows": rows}
	summary = briefing.get("summary") or {}
	if ("Person", summary.get("spouse")) in kept:
		briefing["summary"] = {key: value for key, value in summary.items() if key != "spouse"}
	return briefing


def get_brief_records(briefing: dict) -> list[tuple[str, str]]:
	"""(doctype, name) of each person and record that *briefing* lists."""
	records = [
		get_row_record(part, row)
		for part in (*PEOPLE_PARTS, "open_follow_ups")
		for row in briefing.get(part) or []
	]
	records += [get_card_record(row) for row in (briefing.get("records") or {}).get("rows", [])]
	records.append(("Person", (briefing.get("summary") or {}).get("spouse")))
	return [record for record in records if record and record[1]]


def get_row_record(part: str, row: dict) -> tuple[str, str]:
	return (CARD, row["name"]) if part == "open_follow_ups" else ("Person", row["person"])


def get_card_record(card: dict) -> tuple[str, str] | None:
	"""(doctype, name) of the record a timeline card links to, for a doctype of RECORD_DOCTYPES."""
	url = card.get("url") or ""
	for doctype in RECORD_DOCTYPES:
		prefix = f"{get_url_to_form(doctype)}/"
		if url.startswith(prefix):
			return doctype, unquote(url[len(prefix) :])
	return None


def get_brief_facts(doctype: str, briefing: dict) -> dict:
	"""The parts of *briefing* that BRIEF_PARTS names and that hold something, without links or health fields."""
	facts = {}
	for part in BRIEF_PARTS[doctype]:
		value = briefing.get(part)
		if part == "records":
			value = value["rows"]
		if value:
			facts[part] = without_links(value)
	if "summary" in facts:
		facts["summary"] = {
			key: value
			for key, value in facts["summary"].items()
			if key not in runner.PERSON_HEALTH_FIELDS and (value or key not in SUMMARY_SOURCES)
		}
	return facts


def without_links(value):
	"""*value* with every "url" key left out, at any depth."""
	if isinstance(value, dict):
		return {key: without_links(item) for key, item in value.items() if key != "url"}
	if isinstance(value, list):
		return [without_links(item) for item in value]
	return value


def get_brief_sends(doctype: str, briefing: dict, facts: dict) -> set[str]:
	"""The doctypes of the records *facts* holds; a summary field's doctype comes from SUMMARY_SOURCES
	and a timeline card's from its link."""
	sends = {BRIEF_PARTS[doctype][part] for part in facts}
	sends |= {SUMMARY_SOURCES[key] for key in facts.get("summary", {}) if key in SUMMARY_SOURCES}
	cards = briefing.get("records", {}).get("rows", []) if "records" in facts else []
	return sends | {record[0] for card in cards if (record := get_card_record(card))}


def get_sources(value) -> list[dict]:
	"""Each record *value* links to, at any depth, as title and url, for the dialog's Why line."""
	if isinstance(value, list):
		return [source for item in value for source in get_sources(item)]
	if not isinstance(value, dict):
		return []
	nested = [source for item in value.values() for source in get_sources(item)]
	if not value.get("url"):
		return nested
	title = next((value[key] for key in SOURCE_TITLES if value.get(key)), value.get("name"))
	return [{"title": str(title)[:80], "url": value["url"]}, *nested]


def check_brief(answer: dict) -> dict:
	"""The runner's check for brief: the summary as plain text."""
	summary = answer.get("summary") if isinstance(answer, dict) else None
	if not isinstance(summary, str) or not summary.strip():
		frappe.throw(_("The AI wrote no summary."))
	return {"summary": summary.strip()[:MAX_SUMMARY]}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def draft_note(person: str, text: str, doctype: str = "Person Note") -> dict:
	"""Start an AI run that turns dictated notes about a person into a Person Note or Visitation Log draft. Changes data.

	The prompt holds the notes and the categories, contact methods, visit types and statuses you may
	choose; never the person's record. A Person Note offers only the categories you may add a note
	in. A person who keeps their details out of churchit's AI is refused. The answer comes to your
	browser as the draft's fields; Use opens them in an unsaved form.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	if doctype not in NOTE_DRAFTS:
		frappe.throw(_("Draft a Person Note or a Visitation Log."))
	frappe.has_permission("Person", doc=person, throw=True)
	frappe.has_permission(doctype, "create", throw=True)
	opt_outs.refuse_kept_away("Person", person)
	dictation = check_text(text, MAX_DICTATION)
	choices = get_note_choices(doctype)
	if doctype == "Person Note" and not choices["category"]:
		frappe.throw(_("You may not add a note in any category."), frappe.PermissionError)

	draft = NOTE_DRAFTS[doctype]
	instructions = NOTE_INSTRUCTIONS.format(
		doctype=doctype,
		json_only=JSON_ONLY,
		shape=json.dumps(get_note_shape(doctype)),
		today=today(),
		text_field=draft["text"],
		choices=json.dumps(choices),
	)
	make_access_log(doctype="Person", document=person, method=f"AI: {NOTE_DRAFT}")
	return runner.start(
		NOTE_DRAFT,
		f"{instructions}\n\n{runner.wrap_data(dictation, 'dictated notes')}",
		sends=(doctype,),
		reference_doctype="Person",
		reference_name=person,
		check=draft["check"],
	)


def get_note_shape(doctype: str) -> dict:
	"""The answer a note draft asks for: each field it fills with an example of its type."""
	meta = frappe.get_meta(doctype)
	return {
		fieldname: EXAMPLES.get(meta.get_field(fieldname).fieldtype, "...")
		for fieldname in NOTE_DRAFTS[doctype]["fields"]
	}


def get_note_choices(doctype: str) -> dict[str, list[str]]:
	"""The values the caller may put in each Select and Link field that a note draft fills."""
	meta = frappe.get_meta(doctype)
	choices = {}
	for fieldname in NOTE_DRAFTS[doctype]["fields"]:
		df = meta.get_field(fieldname)
		if df.fieldtype == "Select":
			choices[fieldname] = [option for option in (df.options or "").split("\n") if option]
		elif fieldname == "category":
			categories = notes.search_categories_to_add("Note Category", "", "name", 0, MAX_CHOICES, None)
			choices[fieldname] = [row[0] for row in categories]
		elif df.fieldtype == "Link":
			choices[fieldname] = frappe.get_list(
				df.options, pluck="name", order_by="name asc", limit=MAX_CHOICES
			)
	return choices


def check_person_note(answer: dict) -> dict:
	"""The runner's check for a Person Note draft: its fields, with a category the caller may add."""
	return get_note_values("Person Note", answer)


def check_visitation_log(answer: dict) -> dict:
	"""The runner's check for a Visitation Log draft: its fields, with a visit type the caller may read."""
	return get_note_values("Visitation Log", answer)


def get_note_values(doctype: str, answer: dict) -> dict:
	"""The fields of *answer* a draft of *doctype* takes: listed choices, real dates, whole numbers and the text.

	A value outside the caller's choices is left out, so the person picks it in the form.
	"""
	if not isinstance(answer, dict):
		frappe.throw(_("The AI answer could not be used."))
	meta = frappe.get_meta(doctype)
	choices = get_note_choices(doctype)
	values = {}
	for fieldname in NOTE_DRAFTS[doctype]["fields"]:
		value = get_clean_value(meta.get_field(fieldname), answer.get(fieldname), choices.get(fieldname))
		if value is not None:
			values[fieldname] = value
	if not values.get(NOTE_DRAFTS[doctype]["text"]):
		frappe.throw(_("The AI wrote no note."))
	return {"doctype": doctype, "values": values}


def get_clean_value(df, value, choices: list[str] | None):
	"""*value* when *df* can take it, else None."""
	if choices is not None:
		return value if value in choices else None
	if df.fieldtype == "Date":
		return get_date(value)
	if df.fieldtype == "Int":
		return cint(value) if str(value).isdigit() and 0 < cint(value) <= 24 * 60 else None
	if df.fieldtype == "Check":
		return 1 if value in (True, 1) else 0
	if isinstance(value, str) and value.strip():
		return to_paragraphs(value)
	return None


def get_date(value) -> str | None:
	"""*value* as YYYY-MM-DD when it is a date, else None."""
	try:
		return date.fromisoformat(value).isoformat() if isinstance(value, str) else None
	except ValueError:
		return None


def to_paragraphs(text: str) -> str:
	"""Plain *text* as escaped HTML paragraphs for a Text Editor field, at most MAX_TEXT characters."""
	lines = [line.strip() for line in text[:MAX_TEXT].splitlines() if line.strip()]
	return "".join(f"<p>{escape_html(line)}</p>" for line in lines)


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=RUNS_AN_HOUR, seconds=HOUR, user_based=True)
def suggest_import_mapping(data_import: str) -> dict:
	"""Start an AI run that matches the unknown headings of a churchit import file to its fields. Changes data.

	Only the headings that match no field go to the AI, never a row of the file. The answer comes to
	your browser; Use sets the mapping in the Data Import form, and nothing changes until you save it.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	record = frappe.get_doc("Data Import", data_import)
	record.check_permission("write")
	doctype = record.reference_doctype
	if doctype not in get_import_doctypes():
		frappe.throw(_("Suggest Mapping works on churchit's imports only."))
	frappe.has_permission(doctype, "import", throw=True)
	if not (record.import_file or record.google_sheets_url):
		frappe.throw(_("Attach the file to import first."))

	headings = get_unknown_headings(record)
	if not headings:
		frappe.throw(_("Every heading of this file already matches a field."))
	instructions = IMPORT_INSTRUCTIONS.format(
		doctype=doctype, json_only=JSON_ONLY, fields=json.dumps(get_import_fields(doctype))
	)
	lines = "\n".join(f"{column}: {heading}" for column, heading in headings)
	return runner.start(
		IMPORT_MAPPING,
		f"{instructions}\n\n{runner.wrap_data(lines, 'spreadsheet headings')}",
		check=f"{CHECKS}.check_import_mapping",
	)


def get_import_doctypes() -> set[str]:
	"""The import doctypes churchit registers with Data Import (hooks.py data_import_providers)."""
	return set(frappe.get_hooks("data_import_providers", app_name="churchit"))


def get_unknown_headings(record) -> list[tuple[int, str]]:
	"""(column, heading) of each column of the import file that matches no field and is not set to Don't Import."""
	columns = record.get_importer().import_file.columns
	return [
		(column.index, str(column.header_title))
		for column in columns
		if column.header_title and not column.df and not column.map_to_field
	]


def get_import_fields(doctype: str) -> dict[str, str]:
	"""{fieldname: label} of the fields an import of *doctype* takes."""
	return {
		df.fieldname: _(df.label)
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype not in no_value_fields
	}


def check_import_mapping(answer: dict) -> dict:
	"""The runner's check for suggest_import_mapping: {"import", "mapping": {column: fieldname}}.

	The answer names its import, so the form takes it only for that import. A field the import does
	not take, a field named twice and a column that is not a number are left out.
	"""
	doctype = answer.get("import") if isinstance(answer, dict) else None
	if doctype not in get_import_doctypes() or not frappe.has_permission(doctype, "import"):
		frappe.throw(_("The AI answered for another import."))
	fields = get_import_fields(doctype)
	mapping = {}
	for item in answer.get("mapping") or []:
		column, field = (item.get("column"), item.get("field")) if isinstance(item, dict) else (None, None)
		if str(column).isdigit() and field in fields and field not in mapping.values():
			mapping[str(int(column))] = field
	if not mapping:
		frappe.throw(_("The AI found no field for these headings. Map them by hand."))
	return {"import": doctype, "mapping": mapping}


def check_text(text: str, longest: int) -> str:
	"""*text* without its outer spaces; refuses empty text and text longer than *longest*."""
	text = (text or "").strip() if isinstance(text, str) else ""
	if not text:
		frappe.throw(_("Write something first."))
	if len(text) > longest:
		frappe.throw(_("Use at most {0} characters.").format(longest))
	return text
