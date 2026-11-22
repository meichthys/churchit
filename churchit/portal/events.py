# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Member app endpoints for attendance and function sign-ups.

Writes go through the Function Sign-Up controller, so its rules (seats, waitlist, protected fields,
cancelled sign-ups) apply as they do on the web form.
"""

import html
import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import cint, formatdate, get_datetime, getdate, nowdate, sbool, strip_html_tags

from churchit.church_ministries.doctype.function.function import TIME_FORMAT
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	WINDOW_FIELDS,
	get_item_totals,
	is_open_for_sign_up,
)
from churchit.church_ministries.member_attendance import (
	CHECKED_IN,
	get_member_choices,
	get_own_attendance,
	get_upcoming_sign_ups,
)
from churchit.church_ministries.web_form.function_sign_up.function_sign_up import (
	get_sign_up_summary,
	get_signed_up_functions,
	get_simple_sign_up_functions,
)
from churchit.church_people.member_access import is_portal_member
from churchit.church_scope import church_filters, is_multi_church, session_church
from churchit.portal.access import require_page, require_person
from churchit.utils import LONG_DATE_FORMAT
from churchit.www.register import get_open_functions as get_register_functions

FUNCTION_FIELDS = [
	"name",
	"function_name",
	"start_date",
	"start_time",
	"all_day",
	"question_set",
	"description",
]


def get_function_facts(rows: list) -> dict[str, dict]:
	"""Name, date and time of the functions in *rows*, by function name."""
	names = list({row.function for row in rows})
	# church-scope: the functions of sign-ups the reader may read
	functions = frappe.get_all(
		"Function", filters={"name": ("in", names or [""])}, fields=["name", "function_name", "start_date"]
	)
	return {function.name: function for function in functions}


def describe_date(value) -> dict:
	"""A date as "YYYY-MM-DD", the short display and the long one for running text."""
	if not value:
		return {"start_date": None, "date_display": "", "date_long": ""}
	return {
		"start_date": str(value),
		"date_display": formatdate(value),
		"date_long": formatdate(value, LONG_DATE_FORMAT),
	}


@frappe.whitelist(methods=["GET"])
def get_attendance() -> dict:
	"""The member's upcoming sign-ups and past attendance. Reads only."""
	person = require_person()
	require_page("attendance")

	choices = list(get_member_choices())
	upcoming = [
		{
			"function": row.name,
			"function_name": row.function_name,
			"status": row.status,
			"sign_up": row.sign_up,
			**describe_date(row.start_date),
		}
		for row in get_upcoming_sign_ups(person)
	]
	past = [
		{
			"function": row.name,
			"function_name": row.function_name,
			"attendance_type": row.attendance_type,
			"is_changeable": bool(choices) and row.attendance_type != CHECKED_IN,
			**describe_date(row.start_date),
		}
		for row in get_own_attendance(person)
	]
	return {"choices": choices, "upcoming": upcoming, "past": past}


def get_items(function: str, sign_up: frappe.model.document.Document | None = None) -> list[dict]:
	"""The items of *function* with what others signed up for, and the quantities *sign_up* brings.

	The caller checked the function.
	"""
	# church-scope: the items of one function the caller has checked
	rows = frappe.get_all(
		"Function Sign-Up Item",
		filters={"parent": function, "parenttype": "Function"},
		fields=["item", "quantity_needed", "is_limited", "description"],
		order_by="idx asc",
	)
	totals = get_item_totals(function, exclude_sign_up=sign_up.name if sign_up else None)
	mine = {row.item: cint(row.my_quantity) for row in (sign_up.table_iprj if sign_up else [])}
	return [
		{
			"item": row.item,
			"description": row.description or "",
			"quantity_needed": cint(row.quantity_needed),
			"quantity_signed_up": totals[row.item]["quantity_signed_up"],
			"my_quantity": mine.get(row.item, 0),
			"is_limited": bool(row.is_limited),
		}
		for row in rows
	]


def get_open_function_rows() -> list[frappe._dict]:
	"""The functions that take sign-ups from the member's church, with the facts the lists show."""
	church = session_church()
	if is_multi_church() and not church:
		return []
	# church-scope: church_filters narrows to the member's church and what is shared with it
	return frappe.get_all(
		"Function",
		filters=church_filters(church, allow_sign_ups=1),
		fields=[*FUNCTION_FIELDS, *WINDOW_FIELDS],
		order_by="start_date, start_time",
	)


def to_plain_text(markup: str) -> str:
	"""Editor HTML as text: paragraphs and breaks become new lines, entities become characters."""
	text = re.sub(r"</p>|<br\s*/?>", "\n", markup or "")
	return html.unescape(strip_html_tags(text)).replace("\xa0", " ").strip()


def format_closing(value) -> str:
	"""A date and time as a date and a time, without seconds."""
	if not value:
		return ""
	moment = get_datetime(value)
	return f"{formatdate(moment.date())} {frappe.utils.format_time(moment.time(), TIME_FORMAT)}"


def describe_function(function, signs_up_in: str, sign_up: str | None = None) -> dict:
	return {
		"name": function.name,
		"function_name": function.function_name,
		"start_time": format_time_value(function.start_time),
		"all_day": bool(function.all_day),
		"description": to_plain_text(function.description),
		"closes": format_closing(function.get("sign_ups_close_on")),
		"signs_up_in": signs_up_in,
		"sign_up": sign_up,
		**describe_date(function.start_date),
	}


def format_time_value(value) -> str | None:
	"""A time of day as "HH:mm:ss", or None."""
	return frappe.utils.format_time(value, "HH:mm:ss") if value else None


def get_app_functions(person: str) -> tuple[list[frappe._dict], list[frappe._dict]]:
	"""The open functions the app signs the member up for, and those left out that /register takes."""
	functions = get_open_function_rows()
	simple = get_simple_sign_up_functions(functions)
	signed_up = get_signed_up_functions(person)

	in_app = [
		function for function in functions if function.name in simple and function.name not in signed_up
	]
	left_out = {function.name for function in functions} - simple - signed_up
	on_register = [
		function
		for function in get_register_functions()
		if function.name in left_out and not function.is_link_only
	]
	return in_app, on_register


@frappe.whitelist(methods=["GET"])
def get_open_functions() -> dict:
	"""The functions the member may sign up for in the app, and those that need the /register page. Reads only."""
	person = require_person()
	require_page("function-sign-up")

	in_app, on_register = get_app_functions(person)
	items = [{**describe_function(function, "app"), "items": get_items(function.name)} for function in in_app]
	items += [describe_function(function, "register") for function in on_register]
	return {"items": items}


@frappe.whitelist(methods=["GET"])
def get_sign_ups() -> dict:
	"""The member's function sign-ups, newest change first. Reads only."""
	person = require_person()
	require_page("function-sign-up")

	filters = {}
	if not is_portal_member():
		filters["or_filters"] = [["owner", "=", frappe.session.user], ["person", "=", person]]
	rows = frappe.get_list(
		"Function Sign-Up",
		fields=["name", "function", "status", "person", "modified"],
		order_by="modified desc",
		limit_page_length=200,
		**filters,
	)
	facts = get_function_facts(rows)
	names = get_attendee_names([row.name for row in rows])

	items = []
	for row in rows:
		function = facts.get(row.function)
		items.append(
			{
				"name": row.name,
				"function": row.function,
				"function_name": function.function_name if function else row.function,
				"status": row.status,
				"attendee_names": names.get(row.name, []),
				"can_cancel": row.status != CANCELLED
				and not has_started(function)
				and frappe.has_permission("Function Sign-Up", "write", doc=row.name),
				**describe_date(function.start_date if function else None),
			}
		)
	return {"items": items}


def has_started(function) -> bool:
	"""True when *function* is today or earlier: a member cancels only before the day."""
	return bool(function and function.start_date and getdate(function.start_date) <= getdate(nowdate()))


def get_attendee_names(sign_ups: list[str]) -> dict[str, list[str]]:
	"""Who comes on each of *sign_ups*, which the caller read with the reader's permissions."""
	# church-scope: the attendees of the sign-ups the reader may read
	attendees = frappe.get_all(
		"Function Sign-Up Attendee",
		filters={"parenttype": "Function Sign-Up", "parent": ("in", sign_ups or [""])},
		fields=["parent", "attendee_name"],
		order_by="idx asc",
	)
	names: dict[str, list[str]] = {}
	for row in attendees:
		names.setdefault(row.parent, []).append(row.attendee_name)
	return names


def can_edit_sign_up(doc) -> bool:
	"""True when the member may change *doc* in the app: theirs, live, open, and a function the app signs up for."""
	if doc.status == CANCELLED or not frappe.has_permission("Function Sign-Up", "write", doc=doc):
		return False
	function = frappe.db.get_value("Function", doc.function, [*FUNCTION_FIELDS, *WINDOW_FIELDS], as_dict=True)
	return (
		bool(function)
		and is_open_for_sign_up(doc.function)
		and bool(get_simple_sign_up_functions([function]))
	)


@frappe.whitelist(methods=["GET"])
def get_sign_up(name: str) -> dict:
	"""One of the member's sign-ups: status, people, items, money, and what they may do with it. Reads only."""
	require_person()
	require_page("function-sign-up")

	frappe.has_permission("Function Sign-Up", "read", doc=name, throw=True)
	doc = frappe.get_doc("Function Sign-Up", name)
	summary = get_sign_up_summary(name)
	facts = get_function_facts([doc])
	function = facts.get(doc.function)
	can_edit = can_edit_sign_up(doc)

	return {
		**summary,
		"status": doc.status,
		"payment_status": doc.payment_status if summary["payment_status"] else "",
		"waits_for": get_waiting_reason(doc),
		"name": doc.name,
		"function": doc.function,
		"function_name": function.function_name if function else doc.function,
		"attending": bool(doc.attending),
		"notes": doc.notes or "",
		"items": get_items(doc.function, doc) if can_edit else get_own_items(doc),
		"can_cancel": summary["can_cancel"] and not has_started(function),
		"can_edit": can_edit,
		"pay_url": doc.pay_url if doc.is_payable and summary["can_cancel"] else "",
		"hold_expires": format_closing(doc.hold_expires_on),
		**describe_date(function.start_date if function else None),
	}


def get_waiting_reason(doc) -> str:
	"""Why a Pending sign-up waits: "payment" for a hold that expires, else "approval"; "" when not Pending."""
	if doc.status != "Pending":
		return ""
	return "payment" if doc.hold_expires_on else "approval"


def get_own_items(doc) -> list[dict]:
	"""The items *doc* brings, from its own rows."""
	return [
		{
			"item": row.item,
			"description": row.description or "",
			"quantity_needed": cint(row.quantity_needed),
			"quantity_signed_up": cint(row.quantity_signed_up),
			"my_quantity": cint(row.my_quantity),
			"is_limited": bool(row.is_limited),
		}
		for row in doc.table_iprj
		if cint(row.my_quantity)
	]


def parse_items(items: str | list | None, function: str) -> list[dict]:
	"""Rows of item and my_quantity from the browser, for items *function* asks for; nothing else is kept."""
	rows = frappe.parse_json(items) if isinstance(items, str) else items
	if rows and not (
		isinstance(rows, list) and all(isinstance(row, dict) and row.get("item") for row in rows)
	):
		frappe.throw(_("The items are not valid."), frappe.ValidationError)

	asked = {row["item"] for row in get_items(function)}
	chosen = [row for row in rows or [] if cint(row.get("my_quantity"))]
	for row in chosen:
		if row["item"] not in asked:
			frappe.throw(
				_("{0} is not asked for at this function.").format(row["item"]), frappe.ValidationError
			)

	return [{"item": row["item"], "my_quantity": cint(row["my_quantity"])} for row in chosen]


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=30, seconds=60 * 60, user_based=True)
def sign_up(
	function: str, attending: str | bool = True, notes: str | None = None, items: str | list | None = None
) -> dict:
	"""Sign the member up for a function that the app signs up for. Sends messages.

	A function with selections or questions signs up on /register instead.
	"""
	person = require_person()
	require_page("function-sign-up")

	if function not in {row.name for row in get_app_functions(person)[0]}:
		frappe.throw(_("This function is not open for you to sign up in the app."), frappe.PermissionError)

	# Set the person here: the controller pins it for a Website User only, and staff sign up too.
	doc = frappe.get_doc(
		{
			"doctype": "Function Sign-Up",
			"function": function,
			"person": person,
			"attending": int(sbool(attending)),
			"notes": notes,
			"table_iprj": parse_items(items, function),
		}
	).insert()
	return describe_result(doc)


def describe_result(doc) -> dict:
	"""What the app shows right after a sign-up is saved."""
	summary = get_sign_up_summary(doc.name)
	return {
		"name": doc.name,
		"status": doc.status,
		"waits_for": get_waiting_reason(doc),
		"amount_due": summary["amount_due"],
		"pay_url": doc.pay_url if doc.is_payable else "",
	}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60 * 60, user_based=True)
def update_sign_up(
	name: str, attending: str | bool = True, notes: str | None = None, items: str | list | None = None
) -> dict:
	"""Change whether the member attends, the notes and the items they bring on their sign-up. Sends messages.

	The function never changes: a different function needs a new sign-up.
	"""
	require_person()
	require_page("function-sign-up")

	doc = frappe.get_doc("Function Sign-Up", name)
	doc.check_permission("write")
	if not can_edit_sign_up(doc):
		frappe.throw(_("This sign-up cannot be changed in the app."), frappe.PermissionError)

	doc.attending = int(sbool(attending))
	doc.notes = notes
	doc.set("table_iprj", parse_items(items, doc.function))
	doc.save()
	return describe_result(doc)


@frappe.whitelist(methods=["POST"])
def cancel_sign_up(name: str) -> dict:
	"""Cancel the member's sign-up and give its seats to the waitlist. Sends messages."""
	require_person()
	require_page("function-sign-up")

	doc = frappe.get_doc("Function Sign-Up", name)
	doc.check_permission("write")
	doc.cancel_registration()
	return {"name": doc.name, "status": frappe.db.get_value("Function Sign-Up", name, "status")}
