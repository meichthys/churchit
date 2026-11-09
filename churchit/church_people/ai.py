# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What AI apps and the Church Office agent read about people: smart lists, the office's weekly
questions and briefings.

Each read works as the caller, with the caller's permissions, and returns what the desk would show
them: lists through `frappe.get_list`, counts over Person through `churchit.dashboard`, a script
report through its own role check, a named record through `check_permission`. A list or count of
people covers the reader's churches only, as AGENTS.md asks. A field above the caller's permission
level is left out, never sent as empty. A list sends its first PAGE rows and its total.
"""

import json
from datetime import date
from html import unescape
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.desk import query_report
from frappe.model import get_permitted_fields
from frappe.model.db_query import get_date_range
from frappe.permissions import SYSTEM_USER_ROLE
from frappe.utils import (
	add_days,
	cint,
	get_url_to_form,
	get_url_to_report_with_filters,
	getdate,
	strip_html_tags,
	today,
)
from frappe.utils.data import get_filter

from churchit.ai.switch import require_ai
from churchit.church_people import celebrations, history, notes, smart_lists
from churchit.church_people.doctype.group_join_request.group_join_request import REQUESTED
from churchit.church_people.doctype.marital_status.marital_status import MARRIED
from churchit.church_people.followup import CARD, OPEN
from churchit.church_people.group_leaders import get_leader_roles
from churchit.church_people.group_meetings import MEETING_WEEKS
from churchit.church_people.membership import ACTIVE, MEMBER
from churchit.church_people.summaries.groups import INACTIVE
from churchit.church_scope import church_query_filters
from churchit.dashboard import count_people
from churchit.query import this_week

PAGE = 50
MAX_FILTERS = 10
MAX_COLUMNS = 20
MAX_PEOPLE = 200
MAX_DAYS = 92
MAX_TEXT = 500
LIVING = ["Person", "is_deceased", "=", 0]
DATE_OPERATORS = ("timespan", "previous", "next")
OPERATOR_WORDS = {
	"=": "is",
	"!=": "is not",
	">": "is after or above",
	"<": "is before or below",
	">=": "is on or after, or at least",
	"<=": "is on or before, or at most",
	"like": "contains",
	"not like": "does not contain",
	"in": "is one of",
	"not in": "is none of",
	"between": "is between",
	"timespan": "is within",
	"previous": "is within the previous",
	"next": "is within the next",
}
PERSON_BRIEFING = "AI: Person briefing"
GROUP_BRIEFING = "AI: Group briefing"
# The Person fields a briefing sends, each only when the caller may read it.
PERSON_FIELDS = (
	"full_name",
	"nickname",
	"church",
	"family",
	"spouse",
	"marital_status",
	"gender",
	"age",
	"life_stage",
	"is_deceased",
	"membership",
	"membership_status",
	"primary_email",
	"primary_phone",
	"first_attended_on",
	"last_attended_on",
	"times_attended_90d",
	"last_served_on",
	"times_served_90d",
	"group_count",
	"first_gift_on",
	"last_gift_on",
	"is_lapsed_giver",
	"open_care_requests",
	"last_visited_on",
	"background_check_status",
	"background_check_expires_on",
)
GROUP_FIELDS = (
	"group_name",
	"group_type",
	"status",
	"church",
	"description",
	"meets",
	"public",
	"requires_approval",
	"capacity",
	"close_enrollment_on",
)
# The link a timeline card holds (history_card.html, person_note_card.html), and the icon of a pinned note.
PINNED = "pin"


@frappe.whitelist(methods=["GET"])
def get_smart_list_url(filters: list | str, fields: list | str | None = None) -> dict:
	"""A link to the People report view with *filters*, how many people it shows and the filters in words. Reads only.

	Each filter is [field, operator, value] on Person or [doctype, field, operator, value] on Person or
	one of its child tables (such as Person Group, Person Ministry Team, Person Team Position and Person
	Skill), at most 10. Operators are Frappe's, Timespan included ("last 30 days", "this month").
	*fields* names Person columns to add. The list holds living people unless a filter names
	is_deceased, and only the reader's churches. Returns url, count and explanation: the person opens
	the link, checks the list and uses Save As to keep it as a smart list.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	rows, columns = validate_person_filters(filters, fields)
	if not any(row[1] == "is_deceased" for row in rows):
		rows.insert(0, LIVING)
	count = count_people(rows)["value"]
	return {
		"url": get_people_url(in_readers_churches(rows)),
		"count": count,
		"explanation": describe_people(rows, columns, count),
	}


def validate_person_filters(
	filters: list | dict | str, fields: list | str | None = None
) -> tuple[list[list], list[str]]:
	"""*filters* as [doctype, field, operator, value] rows on Person and its tables, and *fields* as Person fields.

	Refuses more than MAX_FILTERS filters or MAX_COLUMNS fields, and each filter or field that
	`check_filter` or `check_field` refuses.
	"""
	items = get_filter_items(filters)
	columns = frappe.parse_json(fields) or []
	if len(items) > MAX_FILTERS or len(columns) > MAX_COLUMNS:
		frappe.throw(_("Use at most {0} filters and {1} columns.").format(MAX_FILTERS, MAX_COLUMNS))
	for column in columns:
		check_field("Person", column)
	return [check_filter(item) for item in items], columns


def get_filter_items(filters: list | dict | str) -> list[list]:
	"""*filters* as a list of lists; a dict gives one [field, operator, value] for each key.

	A list saved by an older Frappe keeps a fifth element (hidden) on each filter; it is dropped.
	"""
	filters = frappe.parse_json(filters) or []
	if isinstance(filters, dict):
		return [
			[field, *value] if isinstance(value, list | tuple) else [field, "=", value]
			for field, value in filters.items()
		]
	if not isinstance(filters, list) or not all(
		isinstance(item, list | tuple) and len(item) in (3, 4, 5) for item in filters
	):
		frappe.throw(
			_("Give the filters as a list of [field, operator, value] or [doctype, field, operator, value].")
		)
	return [list(item)[:4] for item in filters]


def check_filter(item: list) -> list:
	"""One filter as [doctype, field, operator, value], when Frappe can run it and the caller may read its field."""
	found = get_filter("Person", list(item))
	operator = found.operator.lower()
	if operator in DATE_OPERATORS and not get_date_period(operator, found.value):
		frappe.throw(
			_("Frappe does not know the period {0}, such as last 30 days or this month.").format(found.value)
		)
	check_field(found.doctype, found.fieldname)
	return [found.doctype, found.fieldname, found.operator, found.value]


def get_date_period(operator: str, value) -> tuple | None:
	"""The dates a Timespan, Previous or Next filter covers, as Frappe works them out, or None."""
	try:
		return get_date_range(operator, value)
	except (KeyError, TypeError):
		return None


def check_field(doctype: str, fieldname: str) -> None:
	"""Refuse a field that *doctype*, Person or one of its tables, lacks, or that the caller may not read."""
	person = frappe.get_meta("Person")
	table = next((df for df in person.get_table_fields() if df.options == doctype), None)
	if doctype != "Person" and not table:
		frappe.throw(_("{0} is not Person or one of its tables.").format(doctype))
	meta = frappe.get_meta(doctype)
	if fieldname not in meta.get_valid_columns():
		frappe.throw(_("{0} has no field {1} to filter or show.").format(_(doctype), fieldname))
	readable = fieldname in get_permitted_fields(doctype, parenttype="Person" if table else None)
	if not readable or (table and table.permlevel not in person.get_permlevel_access("read")):
		frappe.throw(_("You may not read {0}.").format(_(meta.get_label(fieldname))), frappe.PermissionError)


def in_readers_churches(filters: list[list]) -> list[list]:
	"""*filters* on Person, narrowed to the churches the reader may see."""
	return [
		*filters,
		*(["Person", field, *condition] for field, condition in church_query_filters({}).items()),
	]


def get_people_url(filters: list[list]) -> str:
	"""The People report view with *filters*, as the desk reads them from the address."""
	params = [
		(field if doctype == "Person" else f"{doctype}.{field}", json.dumps([operator, value], default=str))
		for doctype, field, operator, value in filters
	]
	return get_url_to_report_with_filters("Person", urlencode(params), "Report Builder", "Person")


def describe_people(filters: list[list], fields: list[str], count: int) -> str:
	"""*count* and *filters* in words, the columns to add and how to keep the list."""
	conditions = [describe_filter(row) for row in filters if row != LIVING]
	sentences = [_("Count: {0}.").format(count)]
	if LIVING in filters:
		sentences.append(_("Living people only."))
	if church_query_filters({}):
		sentences.append(_("Only the churches you may see."))
	if conditions:
		sentences.append(_("Filters: {0}.").format("; ".join(conditions)))
	if fields:
		labels = ", ".join(_(frappe.get_meta("Person").get_label(field)) for field in fields)
		sentences.append(_("Add these columns with Pick Columns: {0}.").format(labels))
	sentences.append(_("Open the link, check the list and use Save As to keep it as a smart list."))
	# Frappe keeps the last or default value of a standard filter, such as Membership Status, beside the link's.
	sentences.append(
		_("Remove any filter the report view adds that is not listed here, such as Membership Status.")
	)
	return " ".join(sentences)


def describe_filter(row: list) -> str:
	doctype, fieldname, operator, value = row
	label = _(frappe.get_meta(doctype).get_label(fieldname))
	if doctype != "Person":
		label = f"{_(doctype)}: {label}"
	if isinstance(value, list | tuple):
		value = (" and " if operator.lower() == "between" else ", ").join(map(str, value))
	elif "like" in operator.lower():
		value = str(value).strip("%")
	return f"{label} {_(OPERATOR_WORDS.get(operator.lower(), operator))} {value}"


@frappe.whitelist(methods=["GET"])
def get_smart_list_people(report: str, limit: int = 100) -> list[dict]:
	"""The living people on the smart list *report* in the reader's churches, as name and full_name. Reads only.

	At most 200, by name. A smart list is a saved Report Builder list of people or a saved Attendance
	Count, run with its saved filters.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	frappe.has_permission("Report", doc=report, throw=True)
	if not smart_lists.is_smart_list(report):
		frappe.throw(_("{0} is not a smart list.").format(report))
	source = query_report.get_report_doc(report)
	if source.report_type == smart_lists.SMART_LIST[0]:
		for item in get_filter_items(frappe.parse_json(source.json or "{}").get("filters") or []):
			check_filter(item)

	return frappe.get_list(
		"Person",
		filters=in_readers_churches([["Person", "name", "in", smart_lists.get_people(report, None)]]),
		fields=["name", "full_name"],
		order_by="full_name asc",
		limit=min(max(cint(limit), 1), MAX_PEOPLE),
	)


@frappe.whitelist(methods=["GET"])
def first_time_guests_without_follow_up(days: int = 30) -> dict:
	"""People who first attended in the last *days* days and have no follow-up card. Reads only.

	Living people in the reader's churches; a follow-up card counts whatever its status, when the
	reader may read it. Returns total and rows (the first 50, newest first: name, full_name,
	first_attended_on, url).
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	since = add_days(today(), -check_count(days, 365))
	guests = frappe.get_list(
		"Person",
		filters=in_readers_churches([LIVING, ["Person", "first_attended_on", ">=", since]]),
		fields=["name", "full_name", "first_attended_on"],
		order_by="first_attended_on desc, name asc",
	)
	names = [guest.name for guest in guests]
	followed = set(frappe.get_list(CARD, filters={"person": ("in", names)}, pluck="person"))
	return get_page([with_url("Person", guest) for guest in guests if guest.name not in followed])


@frappe.whitelist(methods=["GET"])
def people_not_seen(weeks: int = 8) -> dict:
	"""Active members who have attended before but not in the last *weeks* weeks. Reads only.

	Living people in the reader's churches, as the Members Not Seen Lately list picks them. Returns
	total, rows (the first 50, most recently seen first: name, full_name, last_attended_on, url) and
	url, the People report view of them all.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	filters = [
		LIVING,
		["Person", "membership", "=", MEMBER],
		["Person", "membership_status", "=", ACTIVE],
		["Person", "last_attended_on", "is", "set"],
		["Person", "last_attended_on", "<", add_days(today(), -7 * check_count(weeks, 104))],
	]
	people = frappe.get_list(
		"Person",
		filters=in_readers_churches(filters),
		fields=["name", "full_name", "last_attended_on"],
		order_by="last_attended_on desc, name asc",
		limit=PAGE,
	)
	rows = [with_url("Person", person) for person in people]
	return get_page(rows, get_people_url(in_readers_churches(filters)), count_people(filters)["value"])


@frappe.whitelist(methods=["GET"])
def birthdays_and_anniversaries(start: str | None = None, end: str | None = None) -> dict:
	"""Birthdays and wedding anniversaries from *start* to *end*, this week (Monday to Sunday) by default. Reads only.

	Living people in the reader's churches, as the desk's birthday and anniversary reports list them;
	a couple once, while both are living. At most 92 days. Returns total and rows (the first 50 by
	date: date, kind Birthday or Anniversary, person, title (the name or the couple), turning or years
	when known, url).
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	start, end = get_window(start, end, this_week())
	rows = [*get_birthdays(start, end), *get_anniversaries(start, end)]
	return get_page(sorted(rows, key=lambda row: (row["date"], row.get("title") or "")))


def get_birthdays(start: date, end: date) -> list[dict]:
	months = sorted({add_days(start, day).month for day in range((end - start).days + 1)})
	people = frappe.get_list(
		"Person",
		filters=in_readers_churches([LIVING, ["Person", "birth_month", "in", months]]),
		fields=["name", "full_name", "birth_month", "birth_day", "birth_date"],
	)
	return [
		{
			"date": row.birthday,
			"kind": "Birthday",
			"person": row.name,
			"title": row.full_name,
			**({"turning": row.age} if row.age else {}),
			"url": get_url_to_form("Person", row.name),
		}
		for row in celebrations.get_birthday_rows(people, start, end)
	]


def get_anniversaries(start: date, end: date) -> list[dict]:
	married = [LIVING, ["Person", "marital_status", "=", MARRIED], ["Person", "anniversary", "is", "set"]]
	people = frappe.get_list(
		"Person",
		filters=in_readers_churches(married),
		fields=["name", "first_name", "last_name", "full_name", "spouse", "anniversary"],
	)
	spouses = [person.spouse for person in people if person.spouse]
	died = set(frappe.get_list("Person", filters={"name": ("in", spouses), "is_deceased": 1}, pluck="name"))
	couples = celebrations.get_anniversary_rows(
		[person for person in people if person.spouse not in died], start, end
	)
	return [
		{
			"date": row.anniversary_on,
			"kind": "Anniversary",
			"person": row.name,
			"title": row.couple,
			"years": row.anniversary_on.year - getdate(row.anniversary).year,
			"url": get_url_to_form("Person", row.name),
		}
		for row in couples
	]


@frappe.whitelist(methods=["GET"])
def groups_needing_attention(weeks: int = 6) -> dict:
	"""Groups that are not Inactive and have no leader, or no meeting in the last *weeks* weeks. Reads only.

	A leader holds a Group Role that leads the group; a meeting is one the Group Attendance report
	counts as held. Returns total and rows (the first 50 by name: name, group_name, reasons, url).
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	since = add_days(today(), -7 * check_count(weeks, 52))
	groups = frappe.get_list(
		"Group",
		filters={"status": ("!=", INACTIVE)},
		fields=["name", "group_name"],
		order_by="group_name asc",
	)
	names = [group.name for group in groups]
	leaders = {"parent": ("in", names), "group_role": ("in", get_leader_roles())}
	led = set(frappe.get_list("Group Member", parent_doctype="Group", filters=leaders, pluck="parent"))
	met = {row.group for row in get_report_rows("Group Attendance", {"from_date": since, "to_date": today()})}
	rows = []
	for group in groups:
		reasons = [
			reason
			for reason, applies in (
				(_("No leader"), group.name not in led),
				(_("No meeting since {0}").format(since), group.name not in met),
			)
			if applies
		]
		if reasons:
			rows.append({**with_url("Group", group), "reasons": reasons})
	return get_page(rows)


@frappe.whitelist(methods=["GET"])
def get_person_briefing(person: str) -> dict:
	"""A person's summary, household, groups, serving, open follow-ups and newest records, with your permissions. Reads only.

	Each field and record comes only when you may read it in the desk, care and giving included; a
	field you may not read is left out. records holds the newest timeline cards (visits, care requests,
	life events, transfers, connection cards and notes) as date, text and url: at most 50, from all
	notes and the newest 20 of each other kind, with total, the number of those cards. Each call is
	kept in the Access Log.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	doc = frappe.get_doc("Person", person)
	doc.check_permission("read")
	make_access_log(doctype="Person", document=doc.name, method=PERSON_BRIEFING)
	doc.apply_fieldlevel_read_permissions()
	summary = get_readable_values(doc, PERSON_FIELDS)
	return {
		"person": doc.name,
		"url": get_url_to_form("Person", doc.name),
		"summary": summary,
		"household": get_household(summary.get("family")),
		"groups": get_titles("Group", [row.group for row in doc.get("groups") or []]),
		"ministry_teams": get_titles("Ministry", [row.ministry for row in doc.get("ministry_teams") or []]),
		"team_positions": get_titles(
			"Ministry Team Position", [row.position for row in doc.get("team_positions") or []]
		),
		"open_follow_ups": get_open_follow_ups(doc.name),
		"records": get_records(doc.name),
	}


def get_readable_values(doc, fields: tuple) -> dict:
	"""The *fields* of *doc* that hold a value, without those apply_fieldlevel_read_permissions removed or masked."""
	masked = doc.flags.masked_fieldnames or set()
	return {
		field: doc.get(field)
		for field in fields
		if hasattr(doc, field) and field not in masked and doc.get(field) not in (None, "")
	}


def get_titles(doctype: str, names: list[str]) -> dict[str, str]:
	"""{name: title} of those of *names* the caller may read."""
	if not names:
		return {}
	title = frappe.get_meta(doctype).title_field or "name"
	return dict(
		frappe.get_list(doctype, filters={"name": ("in", names)}, fields=["name", title], as_list=True)
	)


def get_household(family: str | None) -> list[dict]:
	"""The members of *family* the caller may read, with their household role."""
	if not family or not frappe.has_permission("Family", doc=family):
		return []
	members = frappe.get_list(
		"Family Members",
		parent_doctype="Family",
		filters={"parent": family},
		fields=["member", "household_role"],
		order_by="idx asc",
	)
	names = get_titles("Person", [member.member for member in members])
	return [
		{"person": member.member, "full_name": names[member.member], "household_role": member.household_role}
		for member in members
		if member.member in names
	]


def get_open_follow_ups(person: str) -> list[dict]:
	if not frappe.has_permission(CARD):
		return []
	cards = frappe.get_list(
		CARD,
		filters={"person": person, "status": OPEN},
		fields=["name", "workflow", "step", "due_on"],
		order_by="due_on asc",
		limit=PAGE,
	)
	return [with_url(CARD, card) for card in cards]


def get_records(person: str) -> dict:
	"""The person's timeline cards the caller may read, newest first, as the Person form shows them.

	The timeline reads all notes and the newest 20 records of each other kind, so total counts those
	cards, not every record.
	"""
	cards = [*history.get_timeline_content("Person", person), *notes.get_timeline_notes("Person", person)]
	cards.sort(key=lambda card: card["creation"], reverse=True)
	return get_page([get_card_item(card) for card in cards[:PAGE]], total=len(cards))


def get_card_item(card: dict) -> dict:
	"""A timeline card as its date, its text and its link. A pinned note's date is in its text."""
	item = {"pinned": True} if card["icon"] == PINNED else {"date": card["creation"].date()}
	item["text"] = get_plain_text(card["content"])
	if card["url"]:
		item["url"] = card["url"]
	return item


@frappe.whitelist(methods=["GET"])
def get_group_briefing(group: str) -> dict:
	"""A group's summary, members, leaders, recent meetings with attendance and open join requests, with your permissions. Reads only.

	Each part comes only when you may read it in the desk; a field you may not read is left out.
	members holds the first 50 members, member_count all of them; meetings those of the last 8
	weeks, newest first, with attendance_total. Each call is kept in the Access Log.
	"""
	require_ai()
	frappe.only_for(SYSTEM_USER_ROLE, message=True)
	doc = frappe.get_doc("Group", group)
	doc.check_permission("read")
	make_access_log(doctype="Group", document=doc.name, method=GROUP_BRIEFING)
	doc.apply_fieldlevel_read_permissions()
	as_members = {"parent_doctype": "Group", "fields": ["person", "group_role"], "order_by": "idx asc"}
	members = frappe.get_list("Group Member", filters={"parent": doc.name}, limit=PAGE, **as_members)
	leaders = frappe.get_list(
		"Group Member", filters={"parent": doc.name, "group_role": ("in", get_leader_roles())}, **as_members
	)
	people = get_titles("Person", [row.person for row in [*members, *leaders]])
	return {
		"group": doc.name,
		"url": get_url_to_form("Group", doc.name),
		"summary": get_readable_values(doc, GROUP_FIELDS),
		"member_count": len(doc.get("members") or []),
		"members": [{**row, "full_name": people[row.person]} for row in members if row.person in people],
		"leaders": [{**row, "full_name": people[row.person]} for row in leaders if row.person in people],
		"meetings": get_meetings(doc.name),
		"open_join_requests": get_join_requests(doc.name),
	}


def get_meetings(group: str) -> list[dict]:
	if not frappe.has_permission("Function"):
		return []
	meetings = frappe.get_list(
		"Function",
		filters={
			"group": group,
			"auto_repeat": 0,
			"start_date": ("between", [add_days(today(), -7 * MEETING_WEEKS), today()]),
		},
		fields=["name", "title", "start_date", "did_not_meet", "attendance_total"],
		order_by="start_date desc",
	)
	return [with_url("Function", meeting) for meeting in meetings]


def get_join_requests(group: str) -> list[dict]:
	if not frappe.has_permission("Group Join Request"):
		return []
	requests = frappe.get_list(
		"Group Join Request",
		filters={"group": group, "status": REQUESTED},
		fields=["name", "person", "person_name", "creation"],
		order_by="creation asc",
		limit=PAGE,
	)
	return [with_url("Group Join Request", request) for request in requests]


def get_page(rows: list, url: str | None = None, total: int | None = None) -> dict:
	"""The first PAGE *rows* and their *total* (all of *rows* by default), with the desk *url* that lists them all."""
	page = {"total": len(rows) if total is None else total, "rows": rows[:PAGE]}
	if url:
		page["url"] = url
	return page


def with_url(doctype: str, row: dict) -> dict:
	"""*row*, a record of *doctype*, with the link to its form."""
	row["url"] = get_url_to_form(doctype, row["name"])
	return row


def get_report_rows(report: str, filters: dict) -> list[frappe._dict]:
	"""The rows of the report *report* run with *filters*, with the checks of the desk for the caller."""
	result = query_report.run(report, filters=filters, ignore_prepared_report=True, are_default_filters=False)
	return [frappe._dict(row) for row in result["result"]]


def get_window(start: str | None, end: str | None, default: tuple[date, date]) -> tuple[date, date]:
	"""*start* and *end* as dates, *default* where they are not given. Refuses more than MAX_DAYS days."""
	start = getdate(start) if start else default[0]
	end = getdate(end) if end else add_days(start, (default[1] - default[0]).days)
	if not 0 <= (end - start).days <= MAX_DAYS:
		frappe.throw(_("Ask for {0} days or fewer, with the end on or after the start.").format(MAX_DAYS))
	return start, end


def check_count(value: int, highest: int) -> int:
	"""*value* as a whole number from 1 to *highest*."""
	number = cint(value)
	if not 1 <= number <= highest:
		frappe.throw(_("Ask for a number from 1 to {0}.").format(highest))
	return number


def get_plain_text(html: str | None) -> str:
	"""*html* as one line of plain text, at most MAX_TEXT characters."""
	return " ".join(unescape(strip_html_tags(html or "")).split())[:MAX_TEXT]
