# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Groups in the member app: my groups, one group, the files of my groups, and the leader's page.

Changes go through add_group_file here and the existing endpoints: church_people.group_api (join, leave,
decide, message) and church_people.group_meetings.record_group_attendance.
"""

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import formatdate, get_time, getdate, today

from churchit.church_communications.sending import can_send_texts
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_people.directory import get_primary_emails, get_primary_phones
from churchit.church_people.doctype.group_file.group_file import PRIVATE_FILES, is_web_link
from churchit.church_people.group_api import get_open_join_requests, joinable_public_groups
from churchit.church_people.group_leaders import get_leaders, get_led_groups, require_leader
from churchit.church_people.group_meetings import get_group_meetings, get_meets, get_roster
from churchit.church_people.membership import living_people_filter
from churchit.church_website.pages import get_hidden_pages, is_page_off
from churchit.portal.access import require_page, require_person
from churchit.utils import LONG_DATE_FORMAT

GROUP_FIELDS = ["name", "group_name", "description", "meets"]
UPCOMING_MEETINGS = 6


@frappe.whitelist(methods=["GET"])
def get_my_groups() -> dict:
	"""The groups the member is in, the public groups they may join, and the requests waiting on a leader. Reads only."""
	person = require_person()
	require_page("groups")

	groups = [
		get_group_row(person, row) for row in get_portal_groups(person, GROUP_FIELDS, limit_page_length=0)
	]
	joinable = joinable_public_groups()
	return {
		"groups": groups,
		"joinable": [
			{key: row[key] for key in ("name", "group_name", "description", "requires_approval")}
			for row in joinable
			if not row.requested
		],
		"waiting": [{"name": row.name, "group_name": row.group_name} for row in joinable if row.requested],
	}


@frappe.whitelist(methods=["GET"])
def get_group(group: str) -> dict:
	"""One of the member's groups: where and when it meets, its leaders, later meetings and files. Reads only."""
	person = require_person()
	require_page("groups")

	rows = get_portal_groups(person, GROUP_FIELDS, filters=[["name", "=", group]])
	if not rows:
		frappe.throw(_("You can only open a group you belong to."), frappe.PermissionError)

	result = get_group_row(person, rows[0])
	meetings = get_upcoming_meetings(group)
	result["next_meeting"] = meetings[0] if meetings else None
	result["later_meetings"] = meetings[1:]
	result["show_files"] = not is_page_off("group-files", get_hidden_pages())
	result["files"] = get_files_of(group) if result["show_files"] else []
	return result


@frappe.whitelist(methods=["GET"])
def get_group_files() -> dict:
	"""The files of the member's groups, and the groups they lead and so may add a file to. Reads only."""
	person = require_person()
	require_page("group-files")

	groups = get_file_groups(person)
	return {"items": get_files_of(None), "groups": groups, "can_add": bool(groups)}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60, user_based=True)
def add_group_file(group: str, title: str, attached_file: str) -> dict:
	"""Share a file with a group the member leads. Changes data.

	*attached_file* is a private file the member uploaded or an https link; Group File refuses anything else.
	"""
	require_person()
	require_page("group-files")
	require_leader(group)

	doc = frappe.get_doc(
		{"doctype": "Group File", "group": group, "title": title, "attached_file": attached_file}
	)
	# A leader with a staff role may hold no create right on Group File in the desk.
	doc.insert(ignore_permissions=True)
	return {"name": doc.name}


@frappe.whitelist(methods=["GET"])
def get_leader_view(group: str | None = None) -> dict:
	"""The roster, meetings, join requests and sending options of each group the member leads. Reads only.

	A group name narrows the page to that group, as the link in a reminder email does.
	"""
	person = require_person()
	require_page("group-leader")

	led = get_led_groups(person)
	if group in led:
		led = [group]
	# church-scope: the groups the session Person leads
	names = dict(
		frappe.get_all(
			"Group", filters={"name": ("in", led or [""])}, fields=["name", "group_name"], as_list=True
		)
	)
	requests = get_open_join_requests(led)
	groups = [get_leader_group(name, names[name], requests[name]) for name in sorted(led, key=names.get)]
	return {
		"groups": groups,
		"can_send_email": bool(can_send_email()),
		"can_send_texts": bool(can_send_texts()),
	}


def get_portal_groups(
	person: str | None,
	fields: str | list[str] = "*",
	filters: list | None = None,
	limit_start: int = 0,
	limit_page_length: int = 20,
) -> list[frappe._dict]:
	"""The groups *person* is in that are shown in the portal, plus the groups they lead, with their leaders' names."""
	if not person:
		return []

	# church-scope: the groups of one person's own member rows
	my_groups = frappe.get_all(
		"Group Member", {"person": person, "parenttype": "Group"}, pluck="parent", distinct=True
	)
	led_groups = get_led_groups(person)
	rows = frappe.get_list(
		"Group",
		fields=fields,
		distinct=True,
		filters=[*(filters or []), ["name", "in", my_groups or [""]]],
		or_filters=[["show_in_portal", "=", 1], ["name", "in", led_groups or [""]]],
		limit_start=limit_start,
		limit_page_length=limit_page_length,
		order_by="group_name",
		ignore_permissions=True,
	)
	leaders = get_leader_names([row.name for row in rows]) if rows else {}
	for row in rows:
		row["leaders"] = leaders.get(row.name, "")
	return rows


def get_leader_names(groups: list[str]) -> dict[str, str]:
	"""{group: its living leaders' names, comma separated}: a member sees who leads their own group."""
	# church-scope: the leaders of groups the reader is a member of
	rows = frappe.get_all(
		"Group Member",
		filters={"parenttype": "Group", "parent": ("in", groups), "group_role.is_leader": 1},
		fields=["parent", "person"],
	)
	# church-scope: the leaders' names, a leader being known to their own group
	names = dict(
		frappe.get_all(
			"Person",
			filters=[{"name": ("in", [row.person for row in rows])}, living_people_filter()],
			fields=["name", "full_name"],
			order_by="full_name asc",
			as_list=True,
		)
	)
	leaders: dict[str, list[str]] = {}
	for row in rows:
		if row.person in names:
			leaders.setdefault(row.parent, []).append(names[row.person])
	return {group: ", ".join(sorted(people)) for group, people in leaders.items()}


def get_group_row(person: str, row: frappe._dict) -> dict:
	"""The fields of a group the member page shows, with whether the member leads it or may leave it."""
	leaders = get_leaders(row.name)
	return {
		"name": row.name,
		"group_name": row.group_name,
		"description": row.description or "",
		"meets": row.meets or "",
		"leaders": row.leaders,
		"is_leader": person in leaders,
		"can_leave": leaders != [person],
	}


def get_upcoming_meetings(group: str) -> list[dict]:
	"""The next meetings of *group*, soonest first. The caller has checked that the member is in the group."""
	# church-scope: the meetings of a group the caller found the session Person is in
	rows = frappe.get_all(
		"Function",
		filters={"group": group, "auto_repeat": 0, "start_date": (">=", today())},
		fields=["name", "function_name", "start_date", "start_time", "all_day", "address"],
		order_by="start_date asc, start_time asc",
		limit=UPCOMING_MEETINGS,
	)
	return [
		{
			"name": row.name,
			"title": row.function_name,
			"date": str(getdate(row.start_date)),
			"date_label": formatdate(row.start_date, LONG_DATE_FORMAT),
			"time": None
			if row.all_day or not row.start_time
			else get_time(row.start_time).strftime("%H:%M:%S"),
			"place": row.address and frappe.db.get_value("Address", row.address, "address_title"),
		}
		for row in rows
	]


def get_files_of(group: str | None) -> list[dict]:
	"""The Group Files the session user may read, newest first, of *group* or of all their groups."""
	rows = frappe.get_list(
		"Group File",
		filters={"group": group} if group else {},
		fields=["name", "title", "group", "group_name", "attached_file", "creation"],
		order_by="creation desc",
	)
	return [
		{
			"name": row.name,
			"title": row.title,
			"group": row.group,
			"group_name": row.group_name,
			"file_url": row.attached_file,
			"is_link": is_web_link(row.attached_file),
			"added_on": formatdate(row.creation),
		}
		for row in rows
		# A private upload, or an https link (GroupFile.validate refuses any other link).
		if (row.attached_file or "").startswith((PRIVATE_FILES, "https://"))
	]


def get_file_groups(person: str) -> list[dict]:
	"""The groups *person* leads, as the choices for the group of a new file."""
	# church-scope: only the groups the member leads, whatever their church
	return frappe.get_all(
		"Group",
		filters={"name": ("in", get_led_groups(person) or [""])},
		fields=["name as value", "group_name as label"],
		order_by="group_name",
	)


def get_leader_group(name: str, group_name: str, join_requests: list[frappe._dict]) -> dict:
	"""One led group for the leader page. The caller has checked that the member leads it."""
	meetings = get_group_meetings(name)
	return {
		"name": name,
		"group_name": group_name,
		"roster": [
			{
				"name": member.name,
				"full_name": member.full_name,
				"group_role": member.group_role,
				"email": member.email,
				"phone": member.phone,
			}
			for member in get_contact_roster(name)
		],
		"meetings": [
			{
				"name": meeting.name,
				"title": meeting.function_name,
				"date": str(getdate(meeting.start_date)),
				"time": meeting.start_time and get_time(meeting.start_time).strftime("%H:%M:%S"),
				"did_not_meet": bool(meeting.did_not_meet),
				"attendance_recorded_on": meeting.attendance_recorded_on
				and str(meeting.attendance_recorded_on),
				"attendance": meeting.attendance,
			}
			for meeting in meetings
		],
		"upcoming": None if meetings else get_upcoming_row(name),
		"join_requests": [
			{
				"name": request.name,
				"person_name": request.person_name,
				"message": request.message or "",
				"requested_on": formatdate(request.creation),
			}
			for request in join_requests
		],
	}


def get_upcoming_row(group: str) -> dict:
	upcoming = get_upcoming(group)
	return {
		"next_date": upcoming.next_date and str(getdate(upcoming.next_date)),
		"next_date_label": upcoming.next_date and formatdate(upcoming.next_date, LONG_DATE_FORMAT),
		"has_schedule": upcoming.has_schedule,
	}


def get_upcoming(group: str) -> frappe._dict:
	"""The date of *group*'s next meeting after today, and whether a schedule of the group still runs."""
	# church-scope: the meetings of one group, which the session user leads
	next_date = frappe.db.get_value(
		"Function",
		{"group": group, "auto_repeat": 0, "start_date": (">", today())},
		"start_date",
		order_by="start_date asc",
	)
	return frappe._dict(next_date=next_date, has_schedule=bool(get_meets(group)))


def get_contact_roster(group: str) -> list[frappe._dict]:
	"""*group*'s living members, with the primary email and phone of each who shares them."""
	roster = get_roster(group)
	emails = get_primary_emails([person.name for person in roster if person.share_email])
	phones = get_primary_phones([person.name for person in roster if person.share_phone])
	for person in roster:
		person.email = emails.get(person.name)
		person.phone = phones.get(person.name)
	return roster
