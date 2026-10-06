# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A portal member's own attendance: what they see, and what they may change."""

import frappe
from frappe import _
from frappe.utils import getdate

from churchit.church_scope import session_person

CHECKED_IN = "Checked-In"
# "I was there" and "I was not there". Both ship as fixtures, so they always exist.
MEMBER_CHOICES = ("Confirmed", "Absent")


def get_own_attendance(person):
	"""Functions up to today that list *person* in their attendance, newest first.

	A recurring function copies its attendance roster onto the next occurrence
	before it happens, so a future row is a guess, not a record.
	"""
	rows = frappe.get_all(
		"Function Attendance",
		filters={"person": person, "parenttype": "Function"},
		fields=["parent", "attendance_type"],
	)
	status = {row.parent: row.attendance_type for row in rows}
	if not status:
		return []

	# church-scope: the signed-in member's own attendance, by their person
	functions = frappe.get_all(
		"Function",
		filters={"name": ("in", list(status)), "start_date": ("<=", getdate())},
		fields=["name", "function_name", "start_date"],
		order_by="start_date desc, start_time desc",
	)
	for function in functions:
		function.attendance_type = status[function.name]
	return functions


def get_member_choices():
	"""Attendance types a member may pick, or none when Portal Settings does not allow it."""
	if frappe.db.get_single_value("Portal Settings", "members_can_change_attendance"):
		return MEMBER_CHOICES
	return ()


@frappe.whitelist()
def change_own_attendance(function: str, attendance_type: str):
	"""Set the signed-in member's attendance type on one function their Attendance page lists."""
	if attendance_type not in get_member_choices():
		frappe.throw(_("You cannot choose {0}.").format(attendance_type), frappe.PermissionError)

	person = session_person()
	listed = {row.name: row.attendance_type for row in get_own_attendance(person)} if person else {}
	if function not in listed:
		frappe.throw(_("Your attendance at this function cannot be changed."), frappe.PermissionError)
	if listed[function] == CHECKED_IN:
		frappe.throw(_("You were checked in at this function."), frappe.PermissionError)

	function_doc = frappe.get_doc("Function", function)
	for row in function_doc.attendance:
		if row.person == person:
			row.attendance_type = attendance_type
	# Members cannot write a Function. The checks above confine this save to their own row.
	function_doc.save(ignore_permissions=True)
