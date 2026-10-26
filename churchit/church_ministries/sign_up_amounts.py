# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The money on a Function Sign-Up, worked out only from the Function's own rows.

The browser's prices, `discount` and `amount_due` are never read: each attendee pays the price of
their Selection, each item its Function price times `my_quantity`, and the one largest Discount that
applies comes off, never below 0.
"""

from datetime import date

import frappe
from frappe.utils import cint, flt, getdate, nowdate

CODE, EARLY_BIRD, GROUP, FREELY_GIVEN = "Code", "Early Bird", "Group", "Freely Given"


def get_amount_due(sign_up) -> float:
	subtotal = get_subtotal(sign_up)
	return flt(subtotal - get_discount(sign_up), sign_up.precision("amount_due"))


def get_discount(sign_up) -> float:
	"""The largest Discount of the Function that applies, at most the subtotal."""
	subtotal = get_subtotal(sign_up)
	sign_up_date, code_date = get_sign_up_date(sign_up), get_code_date(sign_up)
	offered = [
		flt(row.amount) or subtotal * flt(row.percent) / 100
		for row in get_function_rows(
			"Function Sign-Up Discount",
			sign_up.function,
			["kind", "code", "amount", "percent", "valid_until", "min_attendees"],
		)
		if is_discount_applicable(row, sign_up, code_date if row.kind == CODE else sign_up_date)
	]
	return flt(min(max([0, *offered]), subtotal), sign_up.precision("discount"))


def get_subtotal(sign_up) -> float:
	selection_prices = {
		row.selection: flt(row.price)
		for row in get_function_rows("Function Sign-Up Selection", sign_up.function, ["selection", "price"])
	}
	item_prices = {
		row.item: flt(row.price)
		for row in get_function_rows("Function Sign-Up Item", sign_up.function, ["item", "price"])
	}
	# set_attendees refuses a new or changed row without one of the Function's selections. A row saved before the
	# Function's selections changed may have none, and costs nothing.
	return sum(selection_prices.get(row.selection, 0) for row in sign_up.attendees) + sum(
		item_prices.get(row.item, 0) * cint(row.my_quantity) for row in sign_up.table_iprj
	)


def is_discount_applicable(row, sign_up, sign_up_date: date) -> bool:
	if row.valid_until and sign_up_date > getdate(row.valid_until):
		return False

	if row.kind == CODE:
		return bool(row.code) and get_code_key(row.code) == get_code_key(sign_up.discount_code)
	if row.kind == EARLY_BIRD:
		return bool(row.valid_until)
	if row.kind == GROUP:
		return bool(row.min_attendees) and len(sign_up.attendees) >= row.min_attendees
	return row.kind == FREELY_GIVEN


def is_freely_given(discounts, on_date: date | None = None) -> bool:
	"""True when a Freely Given row of *discounts* takes the whole price off every sign-up made on *on_date*.

	With no date, only a row with no Valid Until counts, so the price never comes back.
	"""
	return any(
		row.kind == FREELY_GIVEN
		and flt(row.percent) >= 100
		and not flt(row.amount)
		and (not row.valid_until if on_date is None else getdate(row.valid_until or on_date) >= on_date)
		for row in discounts
	)


def get_sign_up_date(sign_up) -> date:
	"""The day the sign-up was made, so a later edit keeps an early bird discount. Frappe refuses a changed `creation`."""
	return getdate(sign_up.creation or nowdate())


def get_code_date(sign_up) -> date:
	"""Today for a code typed now, else the day of sign-up, so a code added after it ends gives nothing."""
	before = sign_up.get_doc_before_save()
	if before and get_code_key(before.discount_code) == get_code_key(sign_up.discount_code):
		return get_sign_up_date(sign_up)
	return getdate(nowdate())


def get_code_key(code: str | None) -> str:
	return (code or "").strip().casefold()


def get_function_rows(doctype: str, function: str, fields: list[str]) -> list:
	# church-scope: the rows of the sign-up's own Function, which its validate checked the reader against
	return frappe.get_all(
		doctype, filters={"parent": function, "parenttype": "Function"}, fields=fields, order_by="idx"
	)
