# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Function Attendance rows: who writes them, and which count as attendance.

A row counts when its type says the person was there and its Function has started. A roster made
ahead of a Function, or a Signed-Up or Absent row, counts in no total, report, card or summary. Every
reader of attendance takes `COUNTED_TYPES` from here and filters `Function.start_date` up to today and
`Function.auto_repeat` to 0: a recurring template is a rule, and its people are a roster that each
occurrence copies. `refuse_a_template` keeps a check-in or a counted row off a template.

`record`, `record_many` and `remove` are the only writers of a person's row. Each loads the Function
under its row lock and saves it whole, so two check-ins at once lose no row, and a desk form opened
before the change fails as stale instead of dropping it. `record_many` gives several people their rows
in one save. The save refreshes the summaries of the people whose rows changed through `doc_events`.
It is not an edit of the Function, so it keeps the Function's Last Edited By (`save_attendance`).
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, getdate, today

# Function Attendance Type is named by its type, so these are also the record names.
COUNTED_TYPES = ("Confirmed", "Assumed", "Checked-In")
REFRESH_DAYS = 7
# A new type replaces a person's type only at the same or a higher rank.
STATUS_RANK = {"Signed-Up": 0, "Assumed": 1, "Confirmed": 2, "Absent": 2, "Checked-In": 3}
OTHER_RANK = 2


def get_total(rows, start_date) -> int:
	"""The head count of a Function's attendance rows: 0 until the Function starts."""
	if getdate(start_date) > getdate():
		return 0
	return sum(1 for row in rows if row.attendance_type in COUNTED_TYPES)


def get_attendance_total(rows, start_date, headcount) -> int:
	"""A Function's `attendance_total`: the larger of its station headcount and its named count, 0 until it starts."""
	if getdate(start_date) > getdate():
		return 0
	return max(get_total(rows, start_date), cint(headcount))


def record(person: str, function: str, status: str) -> bool:
	"""Give *person* the type *status* on *function*, unless their row says more. False when nothing changes."""
	return bool(record_many(function, {person: status}))


def record_many(function: str, statuses: dict[str, str]) -> list[str]:
	"""Give each person in *statuses* their type on *function* in one save, unless their row says more.

	Return the people whose row changed.
	"""
	if not statuses:
		return []
	function_doc = frappe.get_doc("Function", function, for_update=True)
	if set(statuses.values()) & set(COUNTED_TYPES):
		refuse_a_template(function_doc)
	rows = {}
	for row in function_doc.attendance:
		rows.setdefault(row.person, row)

	changed = []
	for person, status in statuses.items():
		row = rows.get(person)
		rank = STATUS_RANK.get(status, OTHER_RANK)
		if row and (row.attendance_type == status or rank < STATUS_RANK.get(row.attendance_type, OTHER_RANK)):
			continue
		# The save skips Frappe's link check of every row, so the links this change writes are checked here.
		refuse_a_missing_record("Person", person)
		refuse_a_missing_record("Function Attendance Type", status)
		if row:
			row.attendance_type = status
		else:
			rows[person] = function_doc.append("attendance", {"person": person, "attendance_type": status})
		changed.append(person)

	if changed:
		save_attendance(function_doc)
	return changed


def refuse_a_template(function) -> None:
	"""Refuse a check-in or counted attendance on a recurring template, which is a rule and not an event."""
	if function.auto_repeat:
		frappe.throw(
			_("{0} is the schedule of a recurring function. Record attendance on one of its dates.").format(
				frappe.bold(function.function_name or function.name)
			)
		)


def refuse_a_missing_record(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("Could not find {0}: {1}").format(_(doctype), name), frappe.LinkValidationError)


def remove(person: str, function: str, status: str) -> bool:
	"""Remove *person*'s row from *function* when its type is *status*. False when there is none."""
	function_doc = frappe.get_doc("Function", function, for_update=True)
	row = next(
		(row for row in function_doc.attendance if (row.person, row.attendance_type) == (person, status)),
		None,
	)
	if not row:
		return False

	function_doc.remove(row)
	save_attendance(function_doc)
	return True


def save_attendance(function_doc: Document) -> None:
	"""Save a change to *function_doc*'s attendance, which is not an edit of the Function.

	It leaves no history entry and puts back who last edited the Function, so a guest's sign-up or a kiosk
	check-in never shows as the last edit. The new `modified` stays, so a form opened before it is stale.
	It skips Frappe's link check, one query per row: the rows it keeps passed it when they were saved, and
	`record_many` checks the links it adds.
	"""
	editor = function_doc.modified_by
	function_doc.flags.ignore_links = True
	# Nothing a website page shows changed, so open pages are not told (church_website/live.py).
	function_doc.flags.attendance_only = True
	function_doc.save(ignore_permissions=True, ignore_version=True)
	frappe.db.set_value("Function", function_doc.name, "modified_by", editor, update_modified=False)
	function_doc.modified_by = editor


def refresh_started_totals():
	"""Daily job: recount the Functions of the last week, so a Function counts its roster once it starts."""
	# church-scope: a job over every church; each total counts only its own Function's rows
	functions = frappe.get_all(
		"Function",
		filters={"start_date": ("between", [add_days(today(), -REFRESH_DAYS), today()]), "auto_repeat": 0},
		pluck="name",
	)
	for name in functions:
		# The lock record() and set_headcount() take, held for one Function at a time.
		function = frappe.get_doc("Function", name, for_update=True)
		total = get_attendance_total(function.attendance, function.start_date, function.headcount)
		if total != function.attendance_total:
			function.db_set("attendance_total", total, update_modified=False)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (free the Function lock per row)


@frappe.whitelist(methods=["POST"])
def set_headcount(function: str, headcount: int) -> int:
	"""Store the headcount the station took in *function*'s room, and return the new total. Changes data.

	The headcount counts everyone in the room, named or not.
	"""
	frappe.has_permission("Function Check-In", "create", throw=True)
	frappe.has_permission("Function", "read", doc=function, throw=True)
	headcount = cint(headcount)
	if headcount < 0:
		frappe.throw(_("A headcount cannot be negative."))

	# The lock record() takes. Church Check-In cannot write Function, so the fields are set directly.
	function_doc = frappe.get_doc("Function", function, for_update=True)
	refuse_a_template(function_doc)
	if getdate(function_doc.start_date) > getdate():
		frappe.throw(_("A headcount can be set only once the function has started."))

	total = get_attendance_total(function_doc.attendance, function_doc.start_date, headcount)
	frappe.db.set_value(
		"Function", function, {"headcount": headcount, "attendance_total": total}, update_modified=True
	)
	return total
