# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A group's meetings: Functions with the group in their Group field."""

from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	escape_html,
	format_date,
	format_time,
	get_url,
	getdate,
	now_datetime,
	sbool,
	today,
)

from churchit.church_communications.doctype.communication_consent.communication_consent import EMAIL
from churchit.church_communications.doctype.communication_purpose.communication_purpose import (
	GROUP_MESSAGES,
)
from churchit.church_communications.sending import send
from churchit.church_ministries.attendance import record
from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import (
	can_send_email,
)
from churchit.church_people.group_leaders import get_leaders, require_leader
from churchit.church_people.membership import living_people_filter

REPEAT_UNITS = {"Daily": "days", "Weekly": "weeks", "Monthly": "months", "Yearly": "years"}
# The leader page shows the meetings of this many weeks back.
MEETING_WEEKS = 8
REMINDER_KEY = "attendance-reminder"
REMINDER_TEMPLATE = "Group Attendance Reminder"


def get_meets(group: str | None) -> str:
	"""When and where *group* meets, from its recurring Function, for the Group's Meets field."""
	if not group:
		return ""
	# church-scope: the schedule of one group, whose Functions take the group's church
	schedules = frappe.get_all(
		"Function",
		filters={"group": group, "auto_repeat": 1},
		fields=[
			"start_date",
			"start_time",
			"all_day",
			"address",
			"repeat_until",
			"repeat_frequency",
			"repeat_interval",
			"repeat_day_of_week",
			"repeat_monthly_by",
			"repeat_week_of_month",
			"repeat_month_day",
		],
		order_by="creation asc",
	)
	today = getdate()
	return "; ".join(
		describe_schedule(schedule)
		for schedule in schedules
		if not schedule.repeat_until or getdate(schedule.repeat_until) >= today
	)


def describe_schedule(schedule) -> str:
	"""One line such as "Weekly on Tuesday at 7:00 PM, Main Hall"."""
	text = describe_schedule_time(schedule)
	place = schedule.address and frappe.db.get_value("Address", schedule.address, "address_title")
	return f"{text}, {place}" if place else text


def describe_schedule_time(schedule) -> str:
	"""When a schedule meets, such as "Weekly on Tuesday at 7:00 PM", without the place."""
	interval = cint(schedule.repeat_interval) or 1
	text = _(schedule.repeat_frequency)
	if interval > 1:
		text = _("Every {0} {1}").format(interval, _(REPEAT_UNITS[schedule.repeat_frequency]))
	day = get_repeat_day(schedule)
	if day:
		text = _("{0} on {1}").format(text, day)
	if schedule.start_time and not schedule.all_day:
		text = _("{0} at {1}").format(text, format_time(schedule.start_time, TIME_FORMAT))
	return text


def get_repeat_day(schedule) -> str | None:
	"""The day of the week, month or year a schedule repeats on."""
	start = getdate(schedule.start_date)
	if schedule.repeat_frequency == "Weekly":
		return _(schedule.repeat_day_of_week or start.strftime("%A"))
	if schedule.repeat_frequency == "Monthly" and schedule.repeat_monthly_by == "Weekday":
		return _("the {0} {1}").format(_(schedule.repeat_week_of_month), _(schedule.repeat_day_of_week))
	if schedule.repeat_frequency == "Monthly":
		return _("day {0}").format(cint(schedule.repeat_month_day) or start.day)
	if schedule.repeat_frequency == "Yearly":
		return format_date(start, "MMMM d")
	return None


def get_roster(group: str) -> list[frappe._dict]:
	"""The living members of *group* by name, with their Group Role and whether they share their email and phone.

	The caller checks that the reader may see them: the leader page and `message_group` ask `require_leader`.
	"""
	# church-scope: the member rows of one group, which the caller leads
	roles = dict(
		frappe.get_all(
			"Group Member",
			filters={"parenttype": "Group", "parent": group},
			fields=["person", "group_role"],
			as_list=True,
		)
	)
	# church-scope: the members of that group, by name
	people = frappe.get_all(
		"Person",
		filters=[{"name": ("in", list(roles))}, living_people_filter()],
		fields=["name", "full_name", "share_email", "share_phone"],
		order_by="full_name asc",
	)
	for person in people:
		person.group_role = roles[person.name]
	return people


def get_group_meetings(group: str) -> list[frappe._dict]:
	"""The meetings of *group* in the last 8 weeks up to today, newest first, each with its attendance by person.

	Only a leader of the group may read them.
	"""
	require_leader(group)
	# church-scope: the meetings of one group, which the session user leads
	meetings = frappe.get_all(
		"Function",
		filters={
			"group": group,
			"auto_repeat": 0,
			"start_date": ("between", [add_days(today(), -7 * MEETING_WEEKS), today()]),
		},
		fields=[
			"name",
			"function_name",
			"start_date",
			"start_time",
			"did_not_meet",
			"attendance_recorded_on",
		],
		order_by="start_date desc, start_time desc",
	)
	# church-scope: the attendance of those meetings
	rows = frappe.get_all(
		"Function Attendance",
		filters={"parenttype": "Function", "parent": ("in", [meeting.name for meeting in meetings])},
		fields=["parent", "person", "attendance_type"],
	)
	for meeting in meetings:
		meeting.attendance = {row.person: row.attendance_type for row in rows if row.parent == meeting.name}
	return meetings


@frappe.whitelist(methods=["POST"])
def record_group_attendance(
	function: str,
	present: str | list[str] | None = None,
	absent: str | list[str] | None = None,
	did_not_meet: str | int = 0,
) -> None:
	"""Leader page: record who came to a meeting of a group the session user leads, or that it did not meet."""
	meeting = frappe.get_doc("Function", function)
	leader = require_leader(meeting.group)
	if meeting.auto_repeat:
		frappe.throw(_("Record the attendance on a meeting, not on the group's schedule."))

	present = frappe.parse_json(present or "[]")
	absent = frappe.parse_json(absent or "[]")
	did_not_meet = sbool(did_not_meet)
	if not did_not_meet:
		# church-scope: the member rows of the group the session user leads
		members = frappe.get_all(
			"Group Member", filters={"parenttype": "Group", "parent": meeting.group}, pluck="person"
		)
		outside = {*present, *absent} - set(members) - {row.person for row in meeting.attendance}
		if outside:
			frappe.throw(_("These people are not in this group: {0}").format(", ".join(sorted(outside))))
		# Members cannot write a Function. The checks above confine these saves to the group's people.
		for person in present:
			record(person, function, "Confirmed")
		for person in absent:
			record(person, function, "Absent")

	meeting.db_set({"did_not_meet": int(did_not_meet), "attendance_recorded_on": now_datetime()})
	leader_name = escape_html(frappe.db.get_value("Person", leader, "full_name"))
	meeting.add_comment(
		"Info",
		_("{0} recorded that the group did not meet.").format(leader_name)
		if did_not_meet
		else _("{0} recorded the attendance: {1} present, {2} absent.").format(
			leader_name, len(present), len(absent)
		),
	)


def send_attendance_reminders() -> None:
	"""Daily job: ask the leaders of yesterday's group meetings to record the attendance.

	The send key makes a second run on the same day send nothing. Nothing is sent while the site has no
	outgoing email account.
	"""
	if not can_send_email():
		return
	# church-scope: a job over every church; each reminder goes to the leaders of its own meeting's group
	meetings = frappe.get_all(
		"Function",
		filters={
			"group": ("is", "set"),
			"auto_repeat": 0,
			"start_date": add_days(today(), -1),
			"attendance_recorded_on": ("is", "not set"),
			"did_not_meet": 0,
		},
		pluck="name",
	)
	for name in meetings:
		meeting = frappe.get_doc("Function", name)
		leaders = get_leaders(meeting.group)
		if not leaders:
			continue
		send(
			leaders,
			EMAIL,
			GROUP_MESSAGES,
			meeting,
			key=REMINDER_KEY,
			template=REMINDER_TEMPLATE,
			context={
				"group_name": frappe.db.get_value("Group", meeting.group, "group_name"),
				"date": format_date(meeting.start_date),
				"link": get_url(f"/group-leader?{urlencode({'group': meeting.group})}"),
			},
		)
