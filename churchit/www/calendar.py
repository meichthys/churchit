# Copyright (c) 2026, meichthys and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_months, getdate


no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "Calendar"
	# Public calendar shows -1 month to +6 months from today.
	today = getdate()
	context.window_start = add_months(today, -1)
	context.window_end = add_months(today, 6)


@frappe.whitelist(allow_guest=True)
def get_events(start, end):
	"""Return published Functions whose start_date falls within [start, end]."""
	start_date = getdate(start)
	end_date = getdate(end)

	# Clamp the requested range to the public window to prevent scraping.
	today = getdate()
	window_start = add_months(today, -1)
	window_end = add_months(today, 6)
	if start_date < window_start:
		start_date = window_start
	if end_date > window_end:
		end_date = window_end

	rows = frappe.get_all(
		"Function",
		filters={
			"publish": 1,
			"start_date": ["between", [start_date, end_date]],
		},
		fields=[
			"name",
			"function_name",
			"title",
			"start_date",
			"start_time",
			"end_date",
			"end_time",
			"all_day",
			"address",
			"description",
			"type",
		],
		order_by="start_date asc, start_time asc",
		limit_page_length=500,
	)

	address_cache = {}
	events = []
	for r in rows:
		start_iso = _combine(r.start_date, r.start_time, r.all_day)
		end_iso = _combine(r.end_date or r.start_date, r.end_time, r.all_day)
		events.append({
			"id": r.name,
			"title": r.function_name or r.title or r.name,
			"start": start_iso,
			"end": end_iso,
			"allDay": bool(r.all_day),
			"type": r.type,
			"address": _format_address(r.address, address_cache),
			"description": r.description,
		})
	return events


def _format_address(address_name, cache):
	"""Render a Function's linked Address as a single readable street line."""
	if not address_name:
		return None
	if address_name in cache:
		return cache[address_name]
	parts = frappe.db.get_value(
		"Address",
		address_name,
		["address_line1", "address_line2", "city", "state", "pincode", "country"],
		as_dict=True,
	) or {}
	pieces = [
		parts.get("address_line1"),
		parts.get("address_line2"),
		", ".join(p for p in [parts.get("city"), parts.get("state"), parts.get("pincode")] if p) or None,
		parts.get("country"),
	]
	formatted = ", ".join(p for p in pieces if p) or address_name
	cache[address_name] = formatted
	return formatted


def _combine(date_value, time_value, all_day):
	"""Build an ISO string FullCalendar v3 accepts."""
	if not date_value:
		return None
	if all_day or not time_value:
		return str(date_value)
	return f"{date_value}T{time_value}"
