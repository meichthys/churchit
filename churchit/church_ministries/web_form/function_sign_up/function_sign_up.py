import json

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate

from churchit.church_finances.doctype.giving_settings.giving_settings import get_currency
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	WAITLISTED,
	WINDOW_FIELDS,
	get_item_totals,
	is_in_sign_up_window,
	is_open_for_sign_up,
)
from churchit.church_people.member_access import hide_edit_unless_writable, is_portal_member
from churchit.church_scope import church_filters, session_church, session_person
from churchit.utils import resolve_link_titles
from churchit.www.register import get_open_functions


def is_over(function) -> bool:
	"""True when a function with no Sign-Ups Close On started before today."""
	return (
		not function.sign_ups_close_on
		and bool(function.start_date)
		and getdate(function.start_date) < getdate()
	)


def get_signed_up_functions(person: str | None) -> set[str]:
	"""The functions *person* already has a live sign-up for: any status but Cancelled."""
	if not person:
		return set()
	# church-scope: the reader's own sign-ups
	return set(
		frappe.get_all(
			"Function Sign-Up", filters={"person": person, "status": ("!=", CANCELLED)}, pluck="function"
		)
	)


def get_simple_sign_up_functions(functions: list) -> set[str]:
	"""The names of *functions* a member signs up for without /register: in the window, not over, no question set, no selections.

	Each function needs its name, question_set, start_date and the window fields.
	"""
	# church-scope: the selections of the functions given
	with_selections = frappe.get_all(
		"Function Sign-Up Selection",
		filters={"parenttype": "Function", "parent": ("in", [function.name for function in functions])},
		pluck="parent",
	)
	return {
		function.name
		for function in functions
		if is_in_sign_up_window(function)
		and not is_over(function)
		and not function.question_set
		and function.name not in with_selections
	}


def get_context(context):
	hide_edit_unless_writable(context, "Function Sign-Up")
	if (context.get("reference_doc") or {}).get("status") == CANCELLED and is_portal_member():
		context.allow_edit = 0  # `refuse_changing_cancelled` refuses the save
	if context.get("reference_doc"):
		# Link fields render as Autocomplete on the portal, which shows the raw docname
		# once the field is read only. Resolve the titles into a separate map for display:
		# rewriting them on reference_doc would leave the client script without the real
		# Function name, which it needs to load that function's sign-up items.
		display_doc = frappe._dict(context.reference_doc)
		resolve_link_titles([display_doc], "Function Sign-Up")
		context.link_titles = {
			"function": display_doc.function,
			"person": display_doc.person,
		}
	functions = frappe.get_all(
		"Function",
		filters=church_filters(session_church(), allow_sign_ups=1),
		fields=["name", "question_set", "start_date", *WINDOW_FIELDS],
	)
	sign_up_functions = get_simple_sign_up_functions(functions)
	already_signed_up = set()
	if is_portal_member():
		# The record being edited keeps its own function in the list.
		own_function = (context.get("reference_doc") or {}).get("function")
		already_signed_up = get_signed_up_functions(session_person()) - {own_function}
		sign_up_functions -= already_signed_up
	context.has_sign_up_functions = bool(sign_up_functions)
	# The form leaves out the functions with options or questions; it links to those that /register takes.
	left_out = {function.name for function in functions} - sign_up_functions - already_signed_up
	context.register_functions = [
		{"name": function.name, "function_name": function.function_name}
		for function in get_open_functions()
		if function.name in left_out and not function.is_link_only
	]

	# Filter the Function autocomplete options to only show functions with sign-ups enabled.
	# Options may be a JSON string of [{value, label}] objects (when show_title_field_in_link
	# is set) or a newline-separated string of names.
	for field in context.get("web_form_doc", {}).get("web_form_fields", []):
		if field.fieldname == "function":
			try:
				options = json.loads(field.options)
				field.options = json.dumps(
					[opt for opt in options if opt.get("value") in sign_up_functions],
					default=str,
				)
			except (json.JSONDecodeError, TypeError, AttributeError):
				options = (field.options or "").split("\n")
				field.options = "\n".join(opt for opt in options if opt in sign_up_functions)
			break


@frappe.whitelist(methods=["GET"])
def get_user_context() -> dict | None:
	"""The signed-in user's Person, and whether they may sign up someone else, for the form. Reads only.

	None for a guest.
	"""
	if frappe.session.user == "Guest":
		return None

	# The form script reads is_manager as "may sign up someone else", which only staff may.
	return {
		"person": session_person(),
		"is_manager": not is_portal_member(),
	}


@frappe.whitelist(methods=["GET"])
def get_function_sign_up_items(function: str) -> list[dict]:
	"""The sign-up items of *function*, with live totals, while the caller may sign up for it. Reads only.

	Members hold no Function DocPerm, so the check is the one the form lists functions by.
	"""
	if not is_open_for_sign_up(function):
		frappe.throw(_("This function is not open for you to sign up."), frappe.PermissionError)
	totals = get_item_totals(function)
	return [
		{
			"item": item,
			"quantity_needed": data["quantity_needed"],
			"quantity_signed_up": data["quantity_signed_up"],
		}
		for item, data in totals.items()
	]


@frappe.whitelist(methods=["GET"])
def get_sign_up_summary(name: str) -> dict:
	"""What the page of sign-up *name* shows: its status, people and money, and if the reader may cancel. Reads only."""
	doc = frappe.get_doc("Function Sign-Up", name)
	doc.check_permission("read")
	currency = get_currency()  # the currency `pay` charges
	# A cancelled or waitlisted sign-up owes nothing now (`get_payment_link`), so only a payment made shows.
	is_live = doc.status != CANCELLED
	owes = doc.status not in (CANCELLED, WAITLISTED) and flt(doc.amount_due) > 0
	return {
		"status": _(doc.status),
		"attendees": [{"name": row.attendee_name, "selection": row.selection or ""} for row in doc.attendees],
		"amount_due": fmt_money(doc.amount_due, currency=currency) if owes else "",
		"amount_paid": fmt_money(doc.amount_paid, currency=currency) if flt(doc.amount_paid) else "",
		"payment_status": _(doc.payment_status) if owes or flt(doc.amount_paid) else "",
		"can_cancel": is_live and frappe.has_permission("Function Sign-Up", "write", doc=doc),
	}
