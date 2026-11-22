# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""A member's sign-ups: the functions they sign up for without /register, and what a sign-up shows them."""

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate

from churchit.church_finances.doctype.giving_settings.giving_settings import get_currency
from churchit.church_ministries.doctype.function_sign_up.function_sign_up import (
	CANCELLED,
	WAITLISTED,
	is_in_sign_up_window,
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


def get_sign_up_summary(name: str) -> dict:
	"""What the page of sign-up *name* shows: its status, people and money, and if the reader may cancel."""
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


def is_over(function) -> bool:
	"""True when a function with no Sign-Ups Close On started before today."""
	return (
		not function.sign_ups_close_on
		and bool(function.start_date)
		and getdate(function.start_date) < getdate()
	)
